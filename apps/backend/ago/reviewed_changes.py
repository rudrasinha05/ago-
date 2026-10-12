"""Exact immutable independent review shared by enterprise extension contexts."""

from __future__ import annotations

import hashlib
import json
from uuid import uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.security_controls import SecurityControls

DOMAINS = {
    "graph": ("knowledge:write", "knowledge"),
    "behavior": ("organization:manage", "operations"),
    "analytics": ("organization:manage", "insights"),
    "integration": ("tool:enroll", "tools"),
}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


class ReviewedChanges:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def require(self, actor: Principal, domain: str) -> None:
        if domain not in DOMAINS:
            raise ValueError("Unknown review domain")
        permission, context = DOMAINS[domain]
        security = self.repositories.resolve(SecurityControls)
        if not security.permitted(
            actor, permission, actor.tenant_id
        ) or not security.constitution_allowed(actor, context):
            raise PermissionError("Current domain authority required")
        human = self.db.execute(
            """SELECT 1 FROM ago_users u JOIN ago_employees e
            ON e.tenant_id=u.tenant_id AND e.id=u.id JOIN ago_user_roles r
            ON r.tenant_id=u.tenant_id AND r.user_id=u.id WHERE u.tenant_id=%s AND u.id=%s
            AND u.active AND e.kind='human' AND r.role='founder'""",
            (actor.tenant_id, actor.subject),
        ).fetchone()
        if not human:
            raise PermissionError("Persisted active human founder required")

    def revision(self, *, tenant_id: str, domain: str) -> int:
        return self.db.execute(
            "SELECT coalesce(max(revision),0) n FROM ago_enterprise_applied WHERE tenant_id=%s AND domain=%s",
            (tenant_id, domain),
        ).fetchone()["n"]

    def propose(
        self,
        *,
        actor: Principal,
        domain: str,
        command: str,
        specification: dict,
        source: dict,
        operation_key: str,
        base_revision: int,
        rationale: str,
    ) -> dict:
        self.require(actor, domain)
        if not 1 <= len(operation_key) <= 160 or not 1 <= len(rationale.strip()) <= 6000:
            raise ValueError("Operation key and rationale required")
        package = dict(
            command=command,
            specification=specification,
            source=source,
            base_revision=base_revision,
            rationale=rationale,
        )
        fingerprint = digest(package)
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            old = self.db.execute(
                "SELECT * FROM ago_enterprise_proposals WHERE tenant_id=%s AND domain=%s AND operation_key=%s",
                (actor.tenant_id, domain, operation_key),
            ).fetchone()
            if old:
                if old["digest"] != fingerprint or str(old["actor_id"]) != actor.subject:
                    raise PermissionError("Changed operation retry")
                return dict(old)
            if type(base_revision) is not int or base_revision != self.revision(
                tenant_id=actor.tenant_id, domain=domain
            ):
                raise PermissionError("Stale reviewed domain revision")
            identifier = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id,
                requester_id=actor.subject,
                action=f"enterprise:review:{domain}:{identifier}:{fingerprint}",
            )
            return dict(
                self.db.execute(
                    """INSERT INTO ago_enterprise_proposals
                (id,tenant_id,domain,actor_id,approval_id,operation_key,base_revision,command,specification,source,rationale,digest)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s) RETURNING *""",
                    (
                        identifier,
                        actor.tenant_id,
                        domain,
                        actor.subject,
                        approval.request_id,
                        operation_key,
                        base_revision,
                        command,
                        canonical(specification),
                        canonical(source),
                        rationale,
                        fingerprint,
                    ),
                ).fetchone()
            )

    def pending(self, *, actor: Principal, domain: str) -> list[dict]:
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "approval:decide", actor.tenant_id
        ):
            raise PermissionError("Independent reviewer permission required")
        return [
            dict(x)
            for x in self.db.execute(
                """SELECT p.*,a.status FROM ago_enterprise_proposals p
            JOIN ago_approval_requests a ON a.tenant_id=p.tenant_id AND a.id=p.approval_id
            WHERE p.tenant_id=%s AND p.domain=%s ORDER BY p.created_at DESC,p.id LIMIT 100""",
                (actor.tenant_id, domain),
            ).fetchall()
        ]

    def package(self, *, actor: Principal, proposal_id: str, domain: str) -> dict:
        self.require(actor, domain)
        self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
        p = self.db.execute(
            "SELECT * FROM ago_enterprise_proposals WHERE tenant_id=%s AND id=%s AND domain=%s",
            (actor.tenant_id, proposal_id, domain),
        ).fetchone()
        if not p or str(p["actor_id"]) != actor.subject:
            raise PermissionError("Original same-tenant author required")
        p = dict(p)
        done = self.db.execute(
            "SELECT * FROM ago_enterprise_applied WHERE tenant_id=%s AND proposal_id=%s",
            (actor.tenant_id, proposal_id),
        ).fetchone()
        if done:
            p["applied"] = dict(done)
            return p
        if p["base_revision"] != self.revision(tenant_id=actor.tenant_id, domain=domain):
            raise PermissionError("Stale proposal; review again")
        a = self.db.execute(
            """SELECT a.* FROM ago_approval_requests a JOIN ago_users u
            ON u.tenant_id=a.tenant_id AND u.id=a.reviewer_id JOIN ago_employees e
            ON e.tenant_id=u.tenant_id AND e.id=u.id WHERE a.tenant_id=%s AND a.id=%s
            AND a.status='approved' AND u.active AND e.kind='human' """,
            (actor.tenant_id, p["approval_id"]),
        ).fetchone()
        if (
            not a
            or str(a["reviewer_id"]) == actor.subject
            or a["action"] != f"enterprise:review:{domain}:{p['id']}:{p['digest']}"
        ):
            raise PermissionError("Exact independent human review required")
        reviewer = Principal(str(a["reviewer_id"]), actor.tenant_id, ("reviewer",))
        if not self.repositories.resolve(SecurityControls).permitted(
            reviewer, "approval:decide", actor.tenant_id
        ):
            raise PermissionError("Reviewer authority revoked")
        return p

    def finish(self, *, actor: Principal, package: dict, result: dict) -> dict:
        row = self.db.execute(
            """INSERT INTO ago_enterprise_applied(id,tenant_id,domain,proposal_id,actor_id,revision,result)
            VALUES(%s,%s,%s,%s,%s,%s,%s::jsonb) RETURNING *""",
            (
                str(uuid4()),
                actor.tenant_id,
                package["domain"],
                package["id"],
                actor.subject,
                package["base_revision"] + 1,
                canonical(result),
            ),
        ).fetchone()
        self.repositories.resolve(SecurityControls).audit(
            "enterprise:applied",
            "allowed",
            tenant_id=actor.tenant_id,
            actor_id=actor.subject,
            metadata={
                "domain": package["domain"],
                "proposal_id": str(package["id"]),
                "digest": package["digest"],
            },
        )
        return dict(row)

    def inspect(self, *, actor: Principal, approval_id: str) -> dict:
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "approval:decide", actor.tenant_id
        ):
            raise PermissionError("Independent review authority required")
        row = self.db.execute(
            "SELECT * FROM ago_enterprise_proposals WHERE tenant_id=%s AND approval_id=%s",
            (actor.tenant_id, approval_id),
        ).fetchone()
        if not row:
            raise LookupError("Exact reviewed source not found")
        return dict(row)
