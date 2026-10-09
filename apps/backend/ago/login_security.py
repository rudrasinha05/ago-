"""Database-backed per-account sign-in throttling for M2 sessions.

Call begin()/success()/failure() within one connection transaction and commit
failed attempts before returning an authentication error.
"""
from __future__ import annotations


class LoginThrottle:
    def __init__(self, connection, *, max_attempts: int = 5):
        if max_attempts < 2:
            raise ValueError("max_attempts must be >= 2")
        self.connection = connection
        self.max_attempts = max_attempts

    def begin(self, tenant_id: str, email: str) -> bool:
        normalized = email.strip().lower()
        if not normalized:
            raise ValueError("Email required")
        exists = self.connection.execute(
            "SELECT 1 FROM ago_tenants WHERE id=%s", (tenant_id,)
        ).fetchone()
        if exists is None:
            return False
        self.connection.execute(
            """INSERT INTO ago_login_attempts(tenant_id,email)
               VALUES (%s,%s) ON CONFLICT DO NOTHING""",
            (tenant_id, normalized),
        )
        row = self.connection.execute(
            """SELECT failures, blocked_until > now() AS blocked
               FROM ago_login_attempts
               WHERE tenant_id=%s AND email=%s FOR UPDATE""",
            (tenant_id, normalized),
        ).fetchone()
        return not bool(row["blocked"])

    def failure(self, tenant_id: str, email: str) -> None:
        self.connection.execute(
            """UPDATE ago_login_attempts
               SET failures=failures+1, updated_at=now(),
                   blocked_until=CASE WHEN failures+1 >= %s
                     THEN now() + interval '15 minutes' ELSE NULL END
               WHERE tenant_id=%s AND email=%s""",
            (self.max_attempts, tenant_id, email.strip().lower()),
        )

    def success(self, tenant_id: str, email: str) -> None:
        self.connection.execute(
            """UPDATE ago_login_attempts
               SET failures=0, blocked_until=NULL, updated_at=now()
               WHERE tenant_id=%s AND email=%s""",
            (tenant_id, email.strip().lower()),
        )
