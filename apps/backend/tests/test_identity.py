import pytest

from ago.identity import IdentityRepository
from ago.security import hash_password


class FakeCursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class FakeConnection:
    def __init__(self):
        self.queries = []
        self.password_hash = hash_password("long-password-123")

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "SELECT id, password_hash" in sql:
            if params[1] == "valid@example.com":
                return FakeCursor({"id": "user-id", "password_hash": self.password_hash})
            return FakeCursor()
        if "SELECT role FROM" in sql:
            return FakeCursor(rows=[{"role": "viewer"}])
        if "RETURNING id" in sql:
            return FakeCursor({"id": "user-id"})
        return FakeCursor()


def test_identity_normalizes_email_and_is_tenant_scoped():
    db = FakeConnection()
    identity = IdentityRepository(db)
    user = identity.create_user("tenant-a", " Valid@Example.com ", "long-password-123")
    assert user.email == "valid@example.com"
    principal = identity.authenticate("tenant-a", " VALID@example.com ", "long-password-123")
    assert principal.subject == "user-id"
    assert principal.tenant_id == "tenant-a"
    assert principal.roles == ("viewer",)
    assert identity.authenticate("tenant-a", "valid@example.com", "wrong") is None
    assert identity.authenticate("tenant-a", "absent@example.com", "long-password-123") is None


def test_role_assignment_and_deactivation_are_tenant_filtered():
    db = FakeConnection()
    identity = IdentityRepository(db)
    identity.assign_role("tenant-a", "user-id", "viewer")
    assert "tenant_id=%s" in db.queries[-1][0]
    assert identity.deactivate_user("tenant-a", "user-id")
    assert "tenant_id=%s" in db.queries[-1][0]


def test_identity_rejects_invalid_input():
    identity = IdentityRepository(FakeConnection())
    with pytest.raises(ValueError):
        identity.create_tenant(" ")
    with pytest.raises(ValueError):
        identity.create_user("tenant", "invalid", "long-password-123")
    with pytest.raises(ValueError):
        identity.assign_role("tenant", "user", "")
