from datetime import datetime, timezone

from ago.security import Principal
from ago.security_controls import SecurityControls


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class DB:
    def __init__(self):
        self.calls = []
        self.found = True

    def execute(self, query, params):
        self.calls.append((query, params))
        return Cursor({"ok": True} if self.found else None)


def test_tenant_scoped_persistent_grants_and_revocation():
    db = DB()
    controls = SecurityControls(db)
    controls.grant("tenant-a", "viewer", "tasks:read")
    assert controls.permitted(Principal("user", "tenant-a", ()), "tasks:read", "tenant-a")
    assert not controls.permitted(
        Principal("user", "tenant-a", ()), "tasks:read", "tenant-b"
    )
    controls.revoke_grant("tenant-a", "viewer", "tasks:read")
    assert "DELETE FROM ago_role_permissions" in db.calls[-1][0]


def test_session_revocation_hashes_token_without_storing_secret():
    db = DB()
    controls = SecurityControls(db)
    controls.revoke_session("secret-token", "tenant-a", datetime.now(timezone.utc))
    assert "secret-token" not in str(db.calls)
    assert controls.is_revoked("secret-token")
    db.found = False
    assert not controls.is_revoked("secret-token")


def test_security_audit_records_structured_metadata():
    db = DB()
    SecurityControls(db).audit(
        "login", "denied", tenant_id="tenant-a", metadata={"reason": "bad_credentials"}
    )
    assert "bad_credentials" in db.calls[-1][1][-1]
