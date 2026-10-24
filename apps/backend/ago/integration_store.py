"""Governed integration identities, durable events, quotas and signed delivery queues."""

from __future__ import annotations

import base64
from dataclasses import asdict
import hashlib
import hmac
import http.client
import ipaddress
import os
import re
import secrets
import socket
import ssl
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.identity_factors import encrypt_factor, decrypt_factor
from ago.reviewed_changes import ReviewedChanges, canonical, digest
from ago.security import Principal, AuthenticationError
from ago.security_controls import SecurityControls
from ago.task_store import TaskStore
from ago import github_adapter
from ago.analytics_store import AnalyticsStore

SCOPES = {"events:read", "tasks:read", "tasks:propose", "analytics:read"}
EVENT_TYPES = {
    "task.changed.v1",
    "approval.changed.v1",
    "integration.changed.v1",
    "report.created.v1",
}
PLUGINS = {"connector", "dashboard", "workflow", "tool", "memory", "evaluation", "reporting"}


def redirect_uri(value):
    p = urlsplit(value)
    if p.username or p.password or p.fragment or not p.hostname or len(value) > 1000:
        raise ValueError("Exact safe redirect URI required")
    if p.scheme != "https" and not (p.scheme == "http" and p.hostname in ("127.0.0.1", "::1")):
        raise ValueError("HTTPS redirect required except native loopback")
    return value


def webhook_url(value):
    p = urlsplit(value)
    if (
        p.scheme != "https"
        or not p.hostname
        or p.port not in (None, 443)
        or p.username
        or p.password
        or p.fragment
        or len(value) > 1000
    ):
        raise ValueError("HTTPS443 webhook without credentials or fragment required")
    try:
        if not ipaddress.ip_address(p.hostname).is_global:
            raise ValueError("Public endpoint required")
    except ValueError as exc:
        if re.fullmatch(r"[0-9a-fA-F:.]+", p.hostname):
            raise ValueError("Public endpoint required") from exc
    if (
        p.hostname.lower().endswith((".localhost", ".local", ".internal"))
        or p.hostname.lower() == "localhost"
    ):
        raise ValueError("Public endpoint required")
    return value


def webhook_signature(secret, timestamp, delivery_id, body):
    return hmac.new(
        secret.encode(),
        str(timestamp).encode() + b"." + delivery_id.encode() + b"." + body,
        hashlib.sha256,
    ).hexdigest()


def verify_webhook(secret, timestamp, delivery_id, body, signature, *, now=None):
    current = int(time.time()) if now is None else now
    if type(timestamp) is not int or abs(current - timestamp) > 300 or len(body) > 65536:
        raise AuthenticationError("Expired or oversized webhook")
    UUID(delivery_id)
    if not hmac.compare_digest(webhook_signature(secret, timestamp, delivery_id, body), signature):
        raise AuthenticationError("Invalid webhook signature")
    return True


def deliver_https(url, body, headers):
    """Pin resolved public IP; verify TLS with original hostname; no proxy or redirects."""
    p = urlsplit(webhook_url(url))
    answers = socket.getaddrinfo(p.hostname, 443, type=socket.SOCK_STREAM)
    ips = list(dict.fromkeys(x[4][0] for x in answers))
    if not ips or any(not ipaddress.ip_address(x).is_global for x in ips):
        raise ValueError("Webhook DNS must resolve only public addresses")
    conn = http.client.HTTPSConnection(
        p.hostname, 443, timeout=3, context=ssl.create_default_context()
    )
    raw = socket.create_connection((ips[0], 443), timeout=3)
    try:
        conn.sock = ssl.create_default_context().wrap_socket(raw, server_hostname=p.hostname)
        conn.request(
            "POST", (p.path or "/") + ("?" + p.query if p.query else ""), body=body, headers=headers
        )
        response = conn.getresponse()
        response.read(1024)
        return response.status
    finally:
        conn.close()
        raw.close()


class IntegrationStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _read(self, actor):
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "tool:read", actor.tenant_id
        ):
            raise PermissionError("Integration read required")

    def _settings(self, tenant, kind, identifier=None):
        rows = self.db.execute(
            """SELECT DISTINCT ON(id) * FROM ago_integration_settings WHERE tenant_id=%s AND kind=%s
            AND (%s::uuid IS NULL OR id=%s) ORDER BY id,revision DESC""",
            (tenant, kind, identifier, identifier),
        ).fetchall()
        return [dict(r) for r in rows]

    def _client(self, tenant, identifier):
        rows = self._settings(tenant, "client", identifier)
        if not rows or not rows[0]["payload"]["enabled"]:
            raise AuthenticationError("Inactive integration client")
        return rows[0]["payload"]

    def catalog(self, *, actor: Principal) -> dict:
        self._read(actor)
        return {
            "revision": self.repositories.resolve(ReviewedChanges).revision(
                tenant_id=actor.tenant_id, domain="integration"
            ),
            "clients": self._settings(actor.tenant_id, "client"),
            "webhooks": self._settings(actor.tenant_id, "webhook"),
            "plugins": self._settings(actor.tenant_id, "plugin"),
            "versions": self._settings(actor.tenant_id, "version"),
            "scopes": sorted(SCOPES),
            "events": sorted(EVENT_TYPES),
            "api_version": "v1",
            "github_projects": self._settings(actor.tenant_id, "github_project"),
            "github_operations": self._settings(actor.tenant_id, "github_operation"),
            "deliveries": [
                dict(r)
                for r in self.db.execute(
                    "SELECT id,subscription_id,event_id,status,attempts,next_attempt_at,last_status FROM ago_webhook_deliveries WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 100",
                    (actor.tenant_id,),
                ).fetchall()
            ],
        }

    def _validate(self, actor, command, p):
        if command in ("github_project", "github_operation"):
            self._validate_github(actor, command, p)
            return
        schemas = {
            "client": {
                "id",
                "name",
                "type",
                "subject_id",
                "department_id",
                "scopes",
                "redirect_uris",
                "enabled",
                "requests_per_minute",
            },
            "webhook": {"id", "client_id", "url", "event_types", "enabled"},
            "plugin": {
                "id",
                "client_id",
                "name",
                "version",
                "extension",
                "state",
                "manifest_sha256",
                "permissions",
                "configuration",
            },
            "version": {"id", "version", "state", "sunset_at", "migration_guide", "schema_digest"},
        }
        if command not in schemas or set(p) != schemas[command]:
            raise ValueError("Strict integration schema required")
        UUID(p["id"])
        if command == "client":
            UUID(p["subject_id"])
            if (
                p["type"] not in ("public", "confidential")
                or type(p["enabled"]) is not bool
                or type(p["requests_per_minute"]) is not int
                or not 1 <= p["requests_per_minute"] <= 600
            ):
                raise ValueError("Explicit client type, enabled state and bounded rate required")
            if not isinstance(p["name"], str) or not 1 <= len(p["name"]) <= 150:
                raise ValueError("Client name required")
            if (
                not isinstance(p["scopes"], list)
                or not p["scopes"]
                or not set(p["scopes"]) <= SCOPES
                or len(p["scopes"]) != len(set(p["scopes"]))
            ):
                raise ValueError("Explicit supported scopes required")
            user = self.db.execute(
                "SELECT 1 FROM ago_users WHERE tenant_id=%s AND id=%s AND active",
                (actor.tenant_id, p["subject_id"]),
            ).fetchone()
            if not user:
                raise PermissionError("Active same-tenant integration principal required")
            if p["department_id"]:
                UUID(p["department_id"])
                if not self.db.execute(
                    "SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, p["department_id"]),
                ).fetchone():
                    raise PermissionError("Foreign department")
            if (
                not isinstance(p["redirect_uris"], list)
                or len(p["redirect_uris"]) > 10
                or (p["type"] == "public" and not p["redirect_uris"])
            ):
                raise ValueError("Bounded exact public redirect registrations required")
            for uri in p["redirect_uris"]:
                redirect_uri(uri)
        elif command == "webhook":
            self._client(actor.tenant_id, p["client_id"])
            webhook_url(p["url"])
            if (
                type(p["enabled"]) is not bool
                or not isinstance(p["event_types"], list)
                or not p["event_types"]
                or not set(p["event_types"]) <= EVENT_TYPES
            ):
                raise ValueError("Supported event subscriptions required")
        elif command == "plugin":
            client = self._client(actor.tenant_id, p["client_id"])
            if (
                p["extension"] not in PLUGINS
                or p["state"]
                not in ("installed", "configured", "enabled", "disabled", "deprecated", "removed")
                or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", p["version"])
            ):
                raise ValueError("Versioned supported plugin lifecycle required")
            if (
                not re.fullmatch(r"[a-f0-9]{64}", p["manifest_sha256"])
                or not isinstance(p["permissions"], list)
                or not set(p["permissions"]) <= set(client["scopes"])
            ):
                raise PermissionError("Pinned manifest and least-privilege client scopes required")
            if (
                not isinstance(p["configuration"], dict)
                or len(canonical(p["configuration"])) > 4000
            ):
                raise ValueError("Bounded nonsecret connector configuration required")
            old = self._settings(actor.tenant_id, "plugin", p["id"])
            transitions = {
                "installed": {"configured", "disabled", "removed"},
                "configured": {"enabled", "disabled", "removed"},
                "enabled": {"enabled", "disabled", "deprecated"},
                "disabled": {"configured", "enabled", "deprecated", "removed"},
                "deprecated": {"disabled", "removed"},
                "removed": set(),
            }
            if (
                not old
                and p["state"] != "installed"
                or old
                and p["state"] not in transitions[old[0]["payload"]["state"]]
            ):
                raise ValueError("Invalid plugin lifecycle transition")
        else:
            if (
                p["version"] != "v1"
                or p["state"] not in ("active", "deprecated", "retired")
                or not re.fullmatch("[a-f0-9]{64}", p["schema_digest"])
            ):
                raise ValueError("Explicit supported API lifecycle required")
            if (
                not isinstance(p["migration_guide"], str)
                or not 1 <= len(p["migration_guide"]) <= 3000
            ):
                raise ValueError("Migration guide required")
            if p["state"] != "active":
                from ago.graph_store import instant

                previous = self._settings(actor.tenant_id, "version")
                old = max(previous, key=lambda r: r["revision"])["payload"] if previous else None
                if p["state"] == "retired":
                    if (
                        not old
                        or old["state"] != "deprecated"
                        or old["sunset_at"] != p["sunset_at"]
                        or instant(p["sunset_at"]) > datetime.now(timezone.utc)
                    ):
                        raise ValueError(
                            "Retirement requires the previously announced elapsed sunset"
                        )
                elif instant(p["sunset_at"]) < datetime.now(timezone.utc) + timedelta(days=30):
                    raise ValueError("At least30 days deprecation notice required")

    def propose(
        self,
        *,
        actor: Principal,
        command: str,
        specification: dict,
        operation_key: str,
        base_revision: int,
        rationale: str,
    ) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        self._validate(actor, command, specification)
        return self.repositories.resolve(ReviewedChanges).propose(
            actor=actor,
            domain="integration",
            command=command,
            specification=specification,
            source=self._integration_source(actor, command, specification),
            operation_key=operation_key,
            base_revision=base_revision,
            rationale=rationale,
        )

    def apply(self, *, actor: Principal, proposal_id: str) -> dict:
        ledger = self.repositories.resolve(ReviewedChanges)
        with self.db.transaction():
            p = ledger.package(actor=actor, proposal_id=proposal_id, domain="integration")
            if p.get("applied"):
                return p["applied"]
            spec = p["specification"]
            self._validate(actor, p["command"], spec)
            if digest(self._integration_source(actor, p["command"], spec)) != digest(p["source"]):
                raise PermissionError("Integration source changed")
            self.db.execute(
                "INSERT INTO ago_integration_settings(tenant_id,id,revision,kind,payload,proposal_id) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    actor.tenant_id,
                    spec["id"],
                    p["base_revision"] + 1,
                    p["command"],
                    canonical(spec),
                    p["id"],
                ),
            )
            if p["command"] == "client":
                self.db.execute(
                    "UPDATE ago_integration_credentials SET revoked_at=clock_timestamp() WHERE tenant_id=%s AND client_id=%s AND revoked_at IS NULL",
                    (actor.tenant_id, spec["id"]),
                )
            return ledger.finish(
                actor=actor, package=p, result={"id": spec["id"], "kind": p["command"]}
            )

    def issue(self, *, actor: Principal, client_id: str, kind: str) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        client = self._client(actor.tenant_id, client_id)
        if kind not in ("api_key", "client_secret") or client["type"] != "confidential":
            raise ValueError("Only confidential clients receive credentials")
        secret = "ago_" + secrets.token_urlsafe(40)
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            self.db.execute(
                "UPDATE ago_integration_credentials SET revoked_at=clock_timestamp() WHERE tenant_id=%s AND client_id=%s AND kind=%s AND revoked_at IS NULL",
                (actor.tenant_id, client_id, kind),
            )
            self.db.execute(
                """INSERT INTO ago_integration_credentials(id,tenant_id,client_id,kind,secret_hash,expires_at,scopes)
                VALUES(%s,%s,%s,%s,%s,clock_timestamp()+interval '30 days',%s)""",
                (
                    str(uuid4()),
                    actor.tenant_id,
                    client_id,
                    kind,
                    hashlib.sha256(secret.encode()).hexdigest(),
                    client["scopes"],
                ),
            )
        self.repositories.resolve(SecurityControls).audit(
            "integration:credential_issued",
            "allowed",
            tenant_id=actor.tenant_id,
            actor_id=actor.subject,
            metadata={"client_id": client_id, "kind": kind},
        )
        return {
            "client_id": client_id,
            "credential": secret,
            "kind": kind,
            "shown_once": True,
            "expires_in": 2592000,
        }

    def _credential(self, secret, kinds):
        if not isinstance(secret, str) or not 40 <= len(secret) <= 256:
            raise AuthenticationError("Invalid integration credential")
        r = self.db.execute(
            "SELECT * FROM ago_integration_credentials WHERE secret_hash=%s AND kind=ANY(%s) AND revoked_at IS NULL AND expires_at>clock_timestamp()",
            (hashlib.sha256(secret.encode()).hexdigest(), list(kinds)),
        ).fetchone()
        if not r:
            raise AuthenticationError("Invalid integration credential")
        client = self._client(str(r["tenant_id"]), str(r["client_id"]))
        if not self.db.execute(
            "SELECT 1 FROM ago_users WHERE tenant_id=%s AND id=%s AND active",
            (r["tenant_id"], client["subject_id"]),
        ).fetchone():
            raise AuthenticationError("Inactive integration subject")
        return dict(r), client

    def authorize(
        self,
        *,
        actor: Principal,
        client_id: str,
        redirect: str,
        challenge: str,
        scopes: list[str],
        state: str,
    ) -> dict:
        client = self._client(actor.tenant_id, client_id)
        if (
            actor.subject != client["subject_id"]
            or redirect not in client["redirect_uris"]
            or not set(scopes) <= set(client["scopes"])
            or not scopes
        ):
            raise PermissionError(
                "Exact registered client, redirect and consenting subject required"
            )
        if not re.fullmatch("[A-Za-z0-9_-]{43}", challenge) or not 16 <= len(state) <= 256:
            raise ValueError("Transaction-specific S256 challenge and state required")
        code = secrets.token_urlsafe(40)
        self.db.execute(
            """INSERT INTO ago_oauth_codes(code_hash,tenant_id,client_id,subject_id,redirect_uri,challenge,scopes,expires_at,client_digest)
            VALUES(%s,%s,%s,%s,%s,%s,%s,clock_timestamp()+interval '2 minutes',%s)""",
            (
                digest(code),
                actor.tenant_id,
                client_id,
                actor.subject,
                redirect,
                challenge,
                scopes,
                digest(client),
            ),
        )
        return {"code": code, "state": state, "redirect_uri": redirect, "expires_in": 120}

    def token(
        self,
        *,
        grant_type: str,
        client_id: str,
        client_secret: str = "",
        code: str = "",
        redirect: str = "",
        verifier: str = "",
        scopes: list[str] | None = None,
        peer: str = "local",
    ) -> dict:
        bucket = int(time.time()) // 60
        hit = self.db.execute(
            "INSERT INTO ago_oauth_throttle(peer_hash,bucket,hits) VALUES(%s,%s,1) ON CONFLICT(peer_hash,bucket) DO UPDATE SET hits=ago_oauth_throttle.hits+1 RETURNING hits",
            (digest(peer), bucket),
        ).fetchone()["hits"]
        if hit > 30:
            raise OverflowError("OAuth endpoint quota exceeded")
        UUID(client_id)
        with self.db.transaction():
            if grant_type == "client_credentials":
                credential, client = self._credential(client_secret, ("client_secret",))
                if str(credential["client_id"]) != client_id or client["type"] != "confidential":
                    raise AuthenticationError("Confidential client required")
                tenant = str(credential["tenant_id"])
                granted = scopes or credential["scopes"]
                if not set(granted) <= set(credential["scopes"]):
                    raise PermissionError("Scope escalation denied")
            elif grant_type == "authorization_code":
                row = self.db.execute(
                    "SELECT * FROM ago_oauth_codes WHERE code_hash=%s FOR UPDATE", (digest(code),)
                ).fetchone()
                if (
                    not row
                    or row["used_at"]
                    or row["expires_at"] <= datetime.now(timezone.utc)
                    or str(row["client_id"]) != client_id
                    or row["redirect_uri"] != redirect
                ):
                    raise AuthenticationError("Invalid or reused authorization code")
                tenant = str(row["tenant_id"])
                client = self._client(tenant, client_id)
                if digest(client) != row["client_digest"] or client["subject_id"] != str(
                    row["subject_id"]
                ):
                    raise AuthenticationError("Registered client changed since consent")
                if client["type"] == "confidential":
                    credential, _ = self._credential(client_secret, ("client_secret",))
                    if str(credential["client_id"]) != client_id:
                        raise AuthenticationError("Wrong client")
                if not re.fullmatch("[A-Za-z0-9._~-]{43,128}", verifier) or not hmac.compare_digest(
                    base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
                    .rstrip(b"=")
                    .decode(),
                    row["challenge"],
                ):
                    raise AuthenticationError("PKCE verification failed")
                self.db.execute(
                    "UPDATE ago_oauth_codes SET used_at=clock_timestamp() WHERE code_hash=%s",
                    (digest(code),),
                )
                granted = row["scopes"]
            else:
                raise ValueError("Unsupported OAuth grant")
            if not set(granted) <= set(client["scopes"]):
                raise PermissionError("Client scopes changed")
            access = "ago_" + secrets.token_urlsafe(40)
            self.db.execute(
                """INSERT INTO ago_integration_credentials(id,tenant_id,client_id,kind,secret_hash,expires_at,scopes)
                VALUES(%s,%s,%s,'access_token',%s,clock_timestamp()+interval '5 minutes',%s)""",
                (
                    str(uuid4()),
                    tenant,
                    client_id,
                    hashlib.sha256(access.encode()).hexdigest(),
                    granted,
                ),
            )
        return {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": 300,
            "scope": " ".join(granted),
        }

    def authenticate(self, *, token: str, scope: str, endpoint: str) -> dict:
        credential, client = self._credential(token, ("api_key", "access_token"))
        if scope not in credential["scopes"] or scope not in client["scopes"]:
            raise PermissionError("Integration scope denied")
        actor = Principal(client["subject_id"], str(credential["tenant_id"]), ("integration",))
        versions = self._settings(str(credential["tenant_id"]), "version")
        if versions:
            version = max(versions, key=lambda r: r["revision"])["payload"]
            if version["state"] != "active":
                from ago.graph_store import instant

                if instant(version["sunset_at"]) <= datetime.now(timezone.utc):
                    raise PermissionError(
                        "API version sunset reached; use the reviewed migration guide"
                    )

        permission = {
            "events:read": "organization:read",
            "tasks:read": "task:read",
            "tasks:propose": "task:create",
            "analytics:read": "insights:read",
        }[scope]
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, permission, actor.tenant_id
        ):
            raise PermissionError("Underlying subject permission revoked")
        context = "tasks" if scope == "tasks:propose" else "tools"
        if not self.repositories.resolve(SecurityControls).constitution_allowed(actor, context):
            raise PermissionError("Constitution blocks integration traffic")
        # Shared database clock and atomic counters enforce tenant, principal, department, client and endpoint quotas across processes.
        with self.db.transaction():
            bucket = int(
                self.db.execute(
                    "SELECT extract(epoch FROM clock_timestamp())::bigint/60 b"
                ).fetchone()["b"]
            )
            axes = [
                ("tenant", actor.tenant_id, 3000),
                ("principal", actor.subject, 1200),
                ("client", str(credential["client_id"]), client["requests_per_minute"]),
                ("endpoint", endpoint, 1500),
            ]
            if client["department_id"]:
                axes.append(("department", client["department_id"], 1500))
            blocked = False
            for kind, key, ceiling in axes:
                count = self.db.execute(
                    """INSERT INTO ago_api_quotas(tenant_id,axis,key,bucket,hits) VALUES(%s,%s,%s,%s,1)
                    ON CONFLICT(tenant_id,axis,key,bucket) DO UPDATE SET hits=ago_api_quotas.hits+1 RETURNING hits""",
                    (actor.tenant_id, kind, key, bucket),
                ).fetchone()["hits"]
                blocked = blocked or count > ceiling
        if blocked:
            self.repositories.resolve(SecurityControls).audit(
                "integration:quota",
                "denied",
                tenant_id=actor.tenant_id,
                actor_id=actor.subject,
                metadata={"client_id": str(credential["client_id"]), "endpoint": endpoint},
            )
            raise OverflowError("Integration rate limit exceeded")
        return {"actor": actor, "client": client, "credential_id": str(credential["id"])}

    def publish(self, *, actor: Principal) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        queued = 0
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            for sub in self._settings(actor.tenant_id, "webhook"):
                p = sub["payload"]
                if not p["enabled"]:
                    continue
                client = self._client(actor.tenant_id, p["client_id"])
                if "events:read" not in client["scopes"]:
                    continue
                rows = self.db.execute(
                    """SELECT ev.id FROM ago_integration_events ev
                    LEFT JOIN ago_employees e ON e.tenant_id=ev.tenant_id AND e.id=ev.subject_id
                    WHERE ev.tenant_id=%s AND ev.event_type=ANY(%s) AND ev.created_at>=%s
                    AND (%s::uuid IS NULL OR e.department_id=%s)
                    AND NOT EXISTS(SELECT 1 FROM ago_webhook_deliveries d WHERE d.tenant_id=ev.tenant_id
                        AND d.subscription_id=%s AND d.event_id=ev.id)
                    ORDER BY ev.sequence LIMIT 500""",
                    (
                        actor.tenant_id,
                        p["event_types"],
                        sub["created_at"],
                        client["department_id"],
                        client["department_id"],
                        sub["id"],
                    ),
                ).fetchall()
                for event in rows:
                    self.db.execute(
                        """INSERT INTO ago_webhook_deliveries(id,tenant_id,subscription_id,event_id)
                        VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                        (str(uuid4()), actor.tenant_id, sub["id"], event["id"]),
                    )
                    queued += 1
        return {
            "queued": queued,
            "source": "transactional explicit integration DTOs",
            "batch_limit_per_subscription": 500,
        }

    def events(self, *, token: str, after: int = 0, limit: int = 100) -> dict:
        if not 0 <= after or not 1 <= limit <= 100:
            raise ValueError("Bounded event cursor required")
        identity = self.authenticate(token=token, scope="events:read", endpoint="events")
        client = identity["client"]
        actor = identity["actor"]
        rows = self.db.execute(
            """SELECT ev.sequence,ev.id,ev.event_type,ev.payload,ev.created_at FROM ago_integration_events ev
            LEFT JOIN ago_employees e ON e.tenant_id=ev.tenant_id AND e.id=ev.subject_id
            WHERE ev.tenant_id=%s AND ev.sequence>%s AND (%s::uuid IS NULL OR e.department_id=%s)
            ORDER BY ev.sequence LIMIT %s""",
            (actor.tenant_id, after, client["department_id"], client["department_id"], limit),
        ).fetchall()
        return {
            "events": [dict(r) for r in rows],
            "next_cursor": rows[-1]["sequence"] if rows else after,
            "schema_version": 1,
        }

    def rotate_webhook(self, *, actor: Principal, subscription_id: str) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        if not self._settings(actor.tenant_id, "webhook", subscription_id):
            raise LookupError("Webhook not found")
        secret = secrets.token_urlsafe(40)
        key_id = str(uuid4())
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            self.db.execute(
                "UPDATE ago_webhook_keys SET active=false WHERE tenant_id=%s AND subscription_id=%s",
                (actor.tenant_id, subscription_id),
            )
            self.db.execute(
                "INSERT INTO ago_webhook_keys(id,tenant_id,subscription_id,ciphertext) VALUES(%s,%s,%s,%s)",
                (
                    key_id,
                    actor.tenant_id,
                    subscription_id,
                    encrypt_factor(secret, actor.tenant_id, subscription_id),
                ),
            )
        return {"key_id": key_id, "secret": secret, "shown_once": True}

    def deliver(self, *, actor: Principal, limit: int = 10) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        if not 1 <= limit <= 20:
            raise ValueError("Delivery batch1..20 required")
        if os.getenv("AGO_WEBHOOK_DELIVERY_ENABLED") != "true":
            raise PermissionError("Webhook network delivery explicitly disabled")
        results = []
        for _ in range(limit):
            with self.db.transaction():
                row = self.db.execute(
                    """SELECT * FROM ago_webhook_deliveries WHERE tenant_id=%s AND status IN ('pending','retry')
                    AND next_attempt_at<=clock_timestamp() ORDER BY next_attempt_at,id FOR UPDATE SKIP LOCKED LIMIT 1""",
                    (actor.tenant_id,),
                ).fetchone()
                if not row:
                    break
                sub = self._settings(actor.tenant_id, "webhook", str(row["subscription_id"]))
                key = self.db.execute(
                    "SELECT * FROM ago_webhook_keys WHERE tenant_id=%s AND subscription_id=%s AND active ORDER BY created_at DESC LIMIT 1",
                    (actor.tenant_id, row["subscription_id"]),
                ).fetchone()
                if not sub or not sub[0]["payload"]["enabled"] or not key:
                    self.db.execute(
                        "UPDATE ago_webhook_deliveries SET status='blocked' WHERE id=%s",
                        (row["id"],),
                    )
                    continue
                event = self.db.execute(
                    "SELECT payload,subject_id FROM ago_integration_events WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, row["event_id"]),
                ).fetchone()
                try:
                    client = self._client(actor.tenant_id, sub[0]["payload"]["client_id"])
                except AuthenticationError:
                    self.db.execute(
                        "UPDATE ago_webhook_deliveries SET status='blocked' WHERE tenant_id=%s AND id=%s",
                        (actor.tenant_id, row["id"]),
                    )
                    continue
                if (
                    client["department_id"]
                    and not self.db.execute(
                        "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND department_id=%s",
                        (actor.tenant_id, event["subject_id"], client["department_id"]),
                    ).fetchone()
                ):
                    self.db.execute(
                        "UPDATE ago_webhook_deliveries SET status='blocked' WHERE id=%s",
                        (row["id"],),
                    )
                    continue
                subject = Principal(client["subject_id"], actor.tenant_id, ("integration",))
                if "events:read" not in client["scopes"] or not self.repositories.resolve(
                    SecurityControls
                ).permitted(subject, "organization:read", actor.tenant_id):
                    self.db.execute(
                        "UPDATE ago_webhook_deliveries SET status='blocked' WHERE id=%s",
                        (row["id"],),
                    )
                    continue
                body = canonical(event["payload"]).encode()
                stamp = int(time.time())
                identifier = str(row["id"])
                secret = decrypt_factor(
                    key["ciphertext"], actor.tenant_id, str(row["subscription_id"])
                )
                headers = {
                    "Content-Type": "application/json",
                    "X-AGO-Delivery": identifier,
                    "X-AGO-Timestamp": str(stamp),
                    "X-AGO-Key": str(key["id"]),
                    "X-AGO-Signature": webhook_signature(secret, stamp, identifier, body),
                }
                status = None
                try:
                    status = deliver_https(sub[0]["payload"]["url"], body, headers)
                except (OSError, ValueError, http.client.HTTPException):
                    pass
                attempts = row["attempts"] + 1
                state = (
                    "delivered"
                    if status and 200 <= status < 300
                    else "dead"
                    if attempts >= 5
                    else "retry"
                )
                self.db.execute(
                    """UPDATE ago_webhook_deliveries SET status=%s,attempts=%s,last_status=%s,
                    next_attempt_at=clock_timestamp()+(%s * interval '1 second') WHERE id=%s""",
                    (state, attempts, status, min(3600, 2**attempts * 10), row["id"]),
                )
                self.db.execute(
                    "INSERT INTO ago_webhook_attempts(tenant_id,delivery_id,attempt,status) VALUES(%s,%s,%s,%s)",
                    (actor.tenant_id, row["id"], attempts, status),
                )
                results.append(
                    {
                        "id": identifier,
                        "status": state,
                        "attempt": attempts,
                        "client_id": client["id"],
                    }
                )
        return {
            "deliveries": results,
            "semantics": "at-least-once; receivers must deduplicate delivery id",
        }

    def replay(self, *, actor: Principal, delivery_id: str, reason: str) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        if not 1 <= len(reason) <= 2000:
            raise ValueError("Replay rationale required")
        row = self.db.execute(
            "UPDATE ago_webhook_deliveries SET status='retry',next_attempt_at=clock_timestamp() WHERE tenant_id=%s AND id=%s AND status IN ('dead','blocked') RETURNING id",
            (actor.tenant_id, delivery_id),
        ).fetchone()
        if not row:
            raise LookupError("Dead or blocked delivery required")
        self.repositories.resolve(SecurityControls).audit(
            "integration:webhook_replay",
            "allowed",
            tenant_id=actor.tenant_id,
            actor_id=actor.subject,
            metadata={"delivery_id": delivery_id, "reason": reason},
        )
        return {"id": delivery_id, "status": "retry"}

    def propose_task(
        self, *, token: str, action: str, assignee_id: str, operation_key: str
    ) -> dict:
        identity = self.authenticate(token=token, scope="tasks:propose", endpoint="tasks")
        actor = identity["actor"]
        client = identity["client"]
        UUID(assignee_id)
        if not 1 <= len(operation_key) <= 160 or not 1 <= len(action) <= 500:
            raise ValueError("Bounded idempotency key and action required")
        if (
            client["department_id"]
            and not self.db.execute(
                "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND department_id=%s",
                (actor.tenant_id, assignee_id, client["department_id"]),
            ).fetchone()
        ):
            raise PermissionError("Integration department scope denied")
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            prior = self.db.execute(
                "SELECT * FROM ago_integration_commands WHERE tenant_id=%s AND client_id=%s AND operation_key=%s",
                (actor.tenant_id, client["id"], operation_key),
            ).fetchone()
            fingerprint = digest({"action": action, "assignee_id": assignee_id})
            if prior:
                if prior["request_digest"] != fingerprint:
                    raise PermissionError("Changed idempotent command")
                return prior["result"]
            result = asdict(
                self.repositories.resolve(TaskStore).propose(
                    tenant_id=actor.tenant_id, action=action, assignee_id=assignee_id
                )
            )
            self.db.execute(
                "INSERT INTO ago_integration_commands(tenant_id,client_id,operation_key,request_digest,result) VALUES(%s,%s,%s,%s,%s::jsonb)",
                (actor.tenant_id, client["id"], operation_key, fingerprint, canonical(result)),
            )
            return result

    def tasks(self, *, token: str, after: str | None = None, limit: int = 50) -> dict:
        identity = self.authenticate(token=token, scope="tasks:read", endpoint="tasks")
        actor = identity["actor"]
        client = identity["client"]
        if not 1 <= limit <= 100:
            raise ValueError("Task page1..100 required")
        if after:
            UUID(after)
        rows = self.db.execute(
            """SELECT t.id,t.status,t.assignee_id,t.created_at,t.updated_at FROM ago_governed_tasks t
            JOIN ago_employees e ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id
            WHERE t.tenant_id=%s AND (%s::uuid IS NULL OR t.id>%s) AND (%s::uuid IS NULL OR e.department_id=%s)
            ORDER BY t.id LIMIT %s""",
            (
                actor.tenant_id,
                after,
                after,
                client["department_id"],
                client["department_id"],
                limit,
            ),
        ).fetchall()
        return {
            "tasks": [dict(r) for r in rows],
            "next_cursor": str(rows[-1]["id"]) if rows else after,
        }

    def _integration_source(self, actor, command, specification):
        source = {"prior": self._settings(actor.tenant_id, command, specification["id"])}
        if command == "github_operation":
            source["project"] = self._github_project(actor, specification["project_id"])
        if command == "github_project":
            source["goal"] = dict(
                self.db.execute(
                    "SELECT * FROM ago_goals WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, specification["goal_id"]),
                ).fetchone()
            )
        return source

    def _validate_github(self, actor, command, p):
        if command == "github_project":
            if set(p) != {
                "id",
                "goal_id",
                "repository",
                "pm_id",
                "developer_ids",
                "qa_id",
                "roadmap_ref",
                "enabled",
            }:
                raise ValueError(
                    "Exact project ownership, roadmap and separation of duties required"
                )
            UUID(p["id"])
            UUID(p["goal_id"])
            github_adapter.repository_name(p["repository"])
            if (
                type(p["enabled"]) is not bool
                or not isinstance(p["roadmap_ref"], str)
                or not 1 <= len(p["roadmap_ref"]) <= 1000
            ):
                raise ValueError("Approved roadmap reference and explicit state required")
            if not self.db.execute(
                "SELECT 1 FROM ago_goals WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, p["goal_id"]),
            ).fetchone():
                raise PermissionError("Same-tenant project goal required")
            if (
                not isinstance(p["developer_ids"], list)
                or not 1 <= len(p["developer_ids"]) <= 20
                or len(set(p["developer_ids"])) != len(p["developer_ids"])
            ):
                raise ValueError("Explicit unique developer identities required")
            if p["qa_id"] in [p["pm_id"], *p["developer_ids"]]:
                raise PermissionError("QA must be independent from project delivery")
            if not self.db.execute(
                "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND kind='ai'",
                (actor.tenant_id, p["pm_id"]),
            ).fetchone():
                raise PermissionError("An accountable AI project manager is required")
            for uid in [p["pm_id"], p["qa_id"], *p["developer_ids"]]:
                UUID(uid)
                if not self.db.execute(
                    "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, uid),
                ).fetchone():
                    raise PermissionError("Same-tenant accountable employee required")
            for old in self._settings(actor.tenant_id, command):
                prior = old["payload"]
                if prior["id"] == p["id"] and (
                    prior["repository"] != p["repository"] or prior["goal_id"] != p["goal_id"]
                ):
                    raise PermissionError("Project repository binding is immutable")
                if prior["id"] != p["id"] and (
                    prior["repository"].lower() == p["repository"].lower()
                    or prior["goal_id"] == p["goal_id"]
                ):
                    raise PermissionError(
                        "Reuse existing project binding; independent projects have separate repositories"
                    )
        else:
            if set(p) != {"id", "project_id", "operation", "payload"}:
                raise ValueError("Exact reviewed GitHub operation required")
            UUID(p["id"])
            UUID(p["project_id"])
            self._github_project(actor, p["project_id"])
            github_adapter.validate_operation(p)
            if self._settings(actor.tenant_id, command, p["id"]):
                raise PermissionError(
                    "GitHub operation is immutable; create a separately reviewed operation"
                )

    def _github_project(self, actor, project_id):
        rows = self._settings(actor.tenant_id, "github_project", project_id)
        if not rows or not rows[0]["payload"]["enabled"]:
            raise PermissionError("Active approved project required")
        return rows[0]["payload"]

    def github_execute(self, *, actor: Principal, operation_id: str) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "integration")
        if os.getenv("AGO_GITHUB_TENANT_ID") != actor.tenant_id:
            raise PermissionError("GitHub credential is not bound to this organization")
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            rows = self._settings(actor.tenant_id, "github_operation", operation_id)
            if not rows:
                raise LookupError("Approved operation required")
            row = rows[0]
            proposal = self.repositories.resolve(ReviewedChanges).package(
                actor=actor, proposal_id=str(row["proposal_id"]), domain="integration"
            )
            if not proposal.get("applied"):
                raise PermissionError("Apply the independently approved operation first")
            # Recheck active reviewer at dispatch, even after local application.
            approval = self.db.execute(
                "SELECT a.reviewer_id FROM ago_approval_requests a JOIN ago_employees e ON e.tenant_id=a.tenant_id AND e.id=a.reviewer_id JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id WHERE a.tenant_id=%s AND a.id=%s AND a.status='approved' AND e.kind='human' AND u.active",
                (actor.tenant_id, proposal["approval_id"]),
            ).fetchone()
            reviewer = (
                Principal(str(approval["reviewer_id"]), actor.tenant_id, ("reviewer",))
                if approval
                else None
            )
            if not reviewer or not self.repositories.resolve(SecurityControls).permitted(
                reviewer, "approval:decide", actor.tenant_id
            ):
                raise PermissionError("Independent reviewer authority revoked")
            operation = row["payload"]
            project = self._github_project(actor, operation["project_id"])
            if project != proposal["source"]["project"]:
                raise PermissionError("Project ownership or policy changed; review operation again")
            old = self.db.execute(
                "SELECT * FROM ago_github_dispatch WHERE tenant_id=%s AND operation_id=%s",
                (actor.tenant_id, operation_id),
            ).fetchone()
            if old:
                if old["status"] == "succeeded":
                    return dict(old)
                raise PermissionError(
                    "Prior delivery may have reached GitHub; inspect the marker before creating a replacement operation"
                )
            binding = self._github_binding(actor, project["id"])
            if operation["operation"] in ("create_repository", "link_repository"):
                if binding:
                    raise PermissionError("Project already has a bound repository; reuse it")
            elif not binding:
                raise PermissionError("Create or link the approved repository first")
            execution_project = {**project, **(binding or {})}
            if os.getenv("AGO_GITHUB_ENABLED") != "true" or not os.getenv("AGO_GITHUB_TOKEN"):
                raise PermissionError(
                    "GitHub owner credential and explicit connector enablement required"
                )
            self.db.execute(
                "INSERT INTO ago_github_dispatch(tenant_id,operation_id,proposal_id,status) VALUES(%s,%s,%s,'started')",
                (actor.tenant_id, operation_id, row["proposal_id"]),
            )
        # Started is durable before network I/O. Uncertain writes are never automatically repeated.
        marker = "ago-operation:" + operation_id
        try:
            result = github_adapter.execute(execution_project, operation, marker)
        except (ValueError, PermissionError, OSError, http.client.HTTPException):
            self.db.execute(
                "UPDATE ago_github_dispatch SET status='uncertain' WHERE tenant_id=%s AND operation_id=%s",
                (actor.tenant_id, operation_id),
            )
            raise ValueError(
                "GitHub delivery uncertain; inspect remote marker before any replacement"
            ) from None
        with self.db.transaction():
            receipt = self.db.execute(
                "UPDATE ago_github_dispatch SET status='succeeded',result=%s::jsonb,completed_at=clock_timestamp() WHERE tenant_id=%s AND operation_id=%s RETURNING *",
                (canonical(result), actor.tenant_id, operation_id),
            ).fetchone()
            # Real GitHub receipts, not speculative tasks, increment project team badges.
            members = {project["pm_id"], project["qa_id"], *project["developer_ids"]}
            operation_kind = operation["operation"]
            files = operation.get("payload", {}).get("files", [])
            category = ("docs" if operation_kind == "commit_files"
                        and any(item["path"].startswith("docs/") for item in files)
                        else "github")
            for employee_id in members:
                self.db.execute("""
                    INSERT INTO ago_company_chat
                    (tenant_id,channel,author_name,body,kind,employee_id)
                    SELECT %s,'employee:' || e.id,'Verified GitHub dispatch',
                      %s,%s,e.id FROM ago_employees e
                    WHERE e.tenant_id=%s AND e.id=%s
                """, (actor.tenant_id, "GitHub "+operation_kind+" succeeded for "+
                       project["repository"], category, actor.tenant_id, employee_id))
        return dict(receipt)

    def github_status(self, *, actor: Principal, project_id: str) -> dict:
        self._read(actor)
        if os.getenv("AGO_GITHUB_TENANT_ID") != actor.tenant_id:
            raise PermissionError("GitHub credential is not bound to this organization")
        p = self._github_project(actor, project_id)
        root = "/repos/" + github_adapter.OWNER + "/" + p["repository"]
        binding = self._github_binding(actor, project_id)
        if not binding:
            return {"project_id": project_id, "status": "repository_not_yet_bound", "ci": []}
        repo = github_adapter.request("GET", root)
        if (
            repo["owner"]["login"].lower() != github_adapter.OWNER
            or repo["id"] != binding["repository_id"]
            or repo["private"] != binding["private"]
        ):
            raise PermissionError("Approved repository identity and visibility required")
        head = github_adapter.request("GET", root + "/git/ref/heads/develop")["object"]["sha"]
        runs = github_adapter.request(
            "GET", root + "/actions/runs?head_sha=" + head + "&per_page=100"
        )
        check_runs = github_adapter.request("GET", root + "/commits/" + head + "/check-runs?per_page=100")
        commit_status = github_adapter.request("GET", root + "/commits/" + head + "/status")
        if not isinstance(check_runs.get("check_runs"), list) or not isinstance(commit_status.get("statuses"), list):
            raise TypeError("GitHub job and commit status evidence required")
        return {
            "project_id": project_id,
            "repository": repo["full_name"],
            "repository_private": repo["private"],
            "develop_sha": head,
            "ci": [
                {
                    "id": r["id"],
                    "name": r["name"],
                    "status": r["status"],
                    "conclusion": r["conclusion"],
                    "url": r["html_url"],
                }
                for r in runs["workflow_runs"]
            ],
            "ci_total": runs["total_count"],
            "ci_truncated": runs["total_count"] > len(runs["workflow_runs"]),
            "ci_check_runs": [
                {"name": c.get("name"), "status": c.get("status"),
                 "conclusion": c.get("conclusion")}
                for c in check_runs["check_runs"]
            ],
            "ci_check_total": check_runs.get(
                "total_count", len(check_runs["check_runs"])
            ),
            "ci_check_truncated": check_runs.get(
                "total_count", len(check_runs["check_runs"])
            ) > len(check_runs["check_runs"]),
            "ci_statuses": [
                {"context": c.get("context"), "state": c.get("state")}
                for c in commit_status["statuses"]
            ],
            "ci_status_truncated": len(commit_status["statuses"]) >= 100,
            "operations": [
                dict(r)
                for r in self.db.execute(
                    "SELECT d.* FROM ago_github_dispatch d JOIN ago_integration_settings s ON s.tenant_id=d.tenant_id AND s.proposal_id=d.proposal_id WHERE d.tenant_id=%s AND s.payload->>'project_id'=%s ORDER BY d.created_at DESC LIMIT 100",
                    (actor.tenant_id, project_id),
                ).fetchall()
            ],
            "release_policy": "Draft PR only; independent human QA and owner release decision required; deletion and transfer unavailable",
        }

    def analytics(self, *, token: str, dashboard: str = "executive") -> dict:
        auth = self.authenticate(token=token, scope="analytics:read", endpoint="analytics")
        actor = auth["actor"]
        result = self.repositories.resolve(AnalyticsStore).dashboard(
            actor=actor,
            dashboard="department" if auth["client"]["department_id"] else dashboard,
            department_id=auth["client"]["department_id"],
        )
        return {
            k: result[k]
            for k in (
                "dashboard",
                "scope",
                "observed_at",
                "definition_version",
                "metrics",
                "task_status",
                "qa_status",
                "limitations",
            )
        }

    def plugin_dispatch(
        self, *, token: str, plugin_id: str, manifest: dict, operation: str, arguments: dict
    ) -> dict:
        scopes = {
            "tasks": "tasks:read",
            "events": "events:read",
            "propose_task": "tasks:propose",
            "analytics": "analytics:read",
        }
        if operation not in scopes:
            raise ValueError("Supported governed adapter operation required")
        auth = self.authenticate(token=token, scope=scopes[operation], endpoint="plugin")
        rows = self._settings(auth["actor"].tenant_id, "plugin", plugin_id)
        if not rows:
            raise PermissionError("Registered plugin required")
        plugin = rows[0]["payload"]
        expected = {
            k: plugin[k] for k in ("name", "version", "extension", "permissions", "configuration")
        }
        if (
            plugin["state"] != "enabled"
            or plugin["client_id"] != auth["client"]["id"]
            or scopes[operation] not in plugin["permissions"]
            or manifest != expected
            or digest(manifest) != plugin["manifest_sha256"]
        ):
            raise PermissionError(
                "Current enabled plugin, pinned manifest and scoped client required"
            )
        methods = {
            "tasks": (self.tasks, {"after", "limit"}),
            "events": (self.events, {"after", "limit"}),
            "propose_task": (self.propose_task, {"action", "assignee_id", "operation_key"}),
            "analytics": (self.analytics, {"dashboard"}),
        }
        method, allowed = methods[operation]
        if set(arguments) - allowed:
            raise ValueError("Unexpected adapter arguments")
        return method(token=token, **arguments)

    def _github_binding(self, actor, project_id):
        row = self.db.execute(
            "SELECT d.result FROM ago_github_dispatch d JOIN ago_integration_settings s ON s.tenant_id=d.tenant_id AND s.proposal_id=d.proposal_id WHERE d.tenant_id=%s AND d.status='succeeded' AND s.payload->>'project_id'=%s AND s.payload->>'operation' IN ('create_repository','link_repository') ORDER BY d.created_at DESC LIMIT 1",
            (actor.tenant_id, project_id),
        ).fetchone()
        return {k: row["result"][k] for k in ("repository_id", "private")} if row else None
