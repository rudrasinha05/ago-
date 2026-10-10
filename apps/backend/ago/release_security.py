"""M10 deployment policy, HTTP perimeter and migration-aware release checks.

Production mode is opt-in and fail-closed. This does not replace a correctly
configured TLS gateway, private egress policies or an independent security audit.
"""
from __future__ import annotations

import hashlib
import ipaddress
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from starlette.middleware.trustedhost import TrustedHostMiddleware

_ALLOWED_ENVIRONMENTS = frozenset({"development", "test", "testing", "staging", "production"})
_HOST = re.compile(
    r"(?i)^(?=.{4,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+$"
)


@dataclass(frozen=True)
class ReleasePolicy:
    environment: str
    hosts: tuple[str, ...]
    body_limit: int

    @property
    def production(self) -> bool:
        return self.environment == "production"

    @classmethod
    def from_environment(cls, environment: str | None = None) -> "ReleasePolicy":
        stage = (environment or os.getenv("AGO_ENVIRONMENT", "development")).lower()
        if stage not in _ALLOWED_ENVIRONMENTS:
            raise ValueError("Unsupported AGO_ENVIRONMENT")
        try:
            cap = int(os.getenv("AGO_MAX_REQUEST_BYTES", "1048576"))
        except ValueError as exc:
            raise ValueError("Invalid AGO_MAX_REQUEST_BYTES") from exc
        if not 256 <= cap <= 2_097_152 or (stage == "production" and cap > 1_048_576):
            raise ValueError("Request body limit outside reviewed bounds")
        raw_hosts = os.getenv("AGO_ALLOWED_HOSTS", "")
        hosts = tuple(part.strip().lower() for part in raw_hosts.split(",") if part.strip())
        if stage == "production":
            validate_production_config(hosts)
        return cls(stage, hosts, cap)


def validate_production_config(hosts: tuple[str, ...]) -> None:
    if not hosts or len(set(hosts)) != len(hosts):
        raise ValueError("Production requires explicit safe public AGO_ALLOWED_HOSTS")
    for name in hosts:
        if not _HOST.fullmatch(name) or name.endswith(
            (".local", ".internal", ".test", ".localhost")
        ):
            raise ValueError("Production requires explicit safe public AGO_ALLOWED_HOSTS")
        try:
            ipaddress.ip_address(name)
        except ValueError:
            continue
        raise ValueError("Production IP literals are not accepted as public hosts")
    secret = os.getenv("AGO_SESSION_SECRET", "")
    if (
        len(secret.encode()) < 48 or len(set(secret)) < 15
        or any(marker in secret.lower() for marker in (
            "ci_only", "example", "placeholder", "change_me", "password",
        ))
    ):
        raise ValueError("Production AGO_SESSION_SECRET is weak or a placeholder")
    dsn = os.getenv("AGO_POSTGRES_DSN", "")
    try:
        parsed = urlsplit(dsn)
        params = parse_qs(parsed.query)
        good_database = (
            parsed.scheme in ("postgresql", "postgres") and
            bool(parsed.hostname) and bool(parsed.path.strip("/")) and
            params.get("sslmode") == ["verify-full"] and
            len(params.get("sslrootcert", [""])[0]) > 1
        )
    except ValueError:
        good_database = False
    if not good_database:
        raise ValueError("Production requires TLS-verified PostgreSQL DSN and CA path")
    if os.getenv("AGO_M8_EXTERNAL_ENABLED", "").lower() == "true":
        raise ValueError("Production disallows unreviewed external metrics egress")
    if os.getenv("AGO_ENABLE_PAID_MODELS", "").lower() == "true":
        raise ValueError("Production disallows unreviewed paid-model egress")
    if os.getenv("AGO_DEBUG", "").lower() == "true":
        raise ValueError("Production debug mode cannot be enabled")


def schema_integrity(dsn: str, directory: Path | None = None) -> bool:
    """Check presence and SHA-256 of every deployed SQL migration, read-only."""
    if directory is None:
        from ago.event_runtime import migration_directory
        directory = migration_directory()
    files = sorted(directory.glob("*.sql")) if directory.is_dir() else []
    if not files:
        return False
    import psycopg
    from psycopg.rows import dict_row

    with psycopg.connect(dsn, connect_timeout=3, row_factory=dict_row) as db:
        rows = db.execute(
            "SELECT filename,sha256 FROM ago_schema_migrations"
        ).fetchall()
    tracked = {str(row["filename"]): str(row["sha256"]) for row in rows}
    expected = {file.name: hashlib.sha256(file.read_bytes()).hexdigest() for file in files}
    return expected == tracked


class BoundedRequestMiddleware:
    """ASGI body cap, including chunked HTTP requests with missing Content-Length.

    Reads at most cap+1 bytes before passing a replayable request to Starlette.
    No application endpoint supports streaming uploads in M1–M10.
    """

    def __init__(self, app, limit: int):
        self.app = app
        self.limit = limit

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from starlette.responses import JSONResponse

        if scope["method"] not in ("POST", "PUT", "PATCH"):
            await self.app(scope, receive, send)
            return
        headers = {k.lower(): v for k, v in scope.get("headers", [])}
        try:
            length = int(headers.get(b"content-length", b"0"))
        except ValueError:
            length = -1
        if length < 0 or length > self.limit:
            await JSONResponse({"detail": "Request body too large"}, status_code=413)(
                scope, receive, send
            )
            return
        chunks = []
        received = 0
        while True:
            event = await receive()
            if event["type"] == "http.disconnect":
                return
            if event["type"] != "http.request":
                continue
            body = event.get("body", b"")
            received += len(body)
            if received > self.limit:
                await JSONResponse({"detail": "Request body too large"}, status_code=413)(
                    scope, receive, send
                )
                return
            chunks.append(body)
            if not event.get("more_body", False):
                break
        buffered = b"".join(chunks)
        delivered = False

        async def replay():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": buffered, "more_body": False}
            return await receive()

        await self.app(scope, replay, send)


class ReleasePerimeterMiddleware:
    """Fail closed for HTTP production business requests and add HTTP headers."""

    def __init__(self, app, production: bool):
        self.app = app
        self.production = production

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        from starlette.responses import JSONResponse

        path = scope.get("path", "")
        scheme = scope.get("scheme", "http")
        # Internal network health probes may be plain HTTP; never include secrets.
        health = path in ("/health/live", "/health/ready")
        if self.production and scheme != "https" and not health:
            await JSONResponse({"detail": "HTTPS required"}, status_code=426)(
                scope, receive, send
            )
            return

        async def secure_start(message):
            if message["type"] == "http.response.start":
                from starlette.datastructures import MutableHeaders
                headers = MutableHeaders(scope=message)
                headers["X-Content-Type-Options"] = "nosniff"
                headers["X-Frame-Options"] = "DENY"
                headers["Referrer-Policy"] = "no-referrer"
                headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
                if path.startswith("/v1/") or health:
                    headers["Cache-Control"] = "no-store, private"
                if self.production and scheme == "https":
                    headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        await self.app(scope, receive, secure_start)


def install_release_perimeter(app, policy: ReleasePolicy) -> None:
    # add_middleware inserts at the outside of prior middleware definitions.
    app.add_middleware(BoundedRequestMiddleware, limit=policy.body_limit)
    app.add_middleware(ReleasePerimeterMiddleware, production=policy.production)
    if policy.production:
        app.add_middleware(
            TrustedHostMiddleware, allowed_hosts=list(policy.hosts),
            www_redirect=False,
        )
