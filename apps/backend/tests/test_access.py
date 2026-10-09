import pytest

from ago.access import AccessService
from ago.security import AuthorizationError, Principal, RolePolicy


class Cursor:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class Connection:
    def __init__(self, active=True, roles=("viewer",)):
        self.active = active
        self.roles = roles
        self.calls = []

    def execute(self, query, params):
        self.calls.append((query, params))
        if "SELECT active" in query:
            return Cursor({"active": self.active})
        return Cursor(rows=[{"role": role} for role in self.roles])


def test_access_denies_cross_tenant_before_database_query():
    db = Connection()
    policy = RolePolicy()
    policy.grant("viewer", "task:read")
    principal = Principal("user", "tenant-a", ("viewer",))
    decision = AccessService(db, policy).evaluate(
        principal, "task:read", resource_tenant_id="tenant-b"
    )
    assert not decision.permitted
    assert not db.calls


def test_access_uses_fresh_persisted_roles():
    db = Connection(roles=("viewer",))
    policy = RolePolicy()
    policy.grant("admin", "task:delete")
    principal = Principal("user", "tenant-a", ("admin",))
    service = AccessService(db, policy)
    assert not service.evaluate(
        principal, "task:delete", resource_tenant_id="tenant-a"
    ).permitted
    with pytest.raises(AuthorizationError):
        service.require(principal, "task:delete", resource_tenant_id="tenant-a")


def test_access_allows_active_user_with_persisted_permission():
    db = Connection()
    policy = RolePolicy()
    policy.grant("viewer", "task:read")
    principal = Principal("user", "tenant-a", ())
    service = AccessService(db, policy)
    service.require(principal, "task:read", resource_tenant_id="tenant-a")


def test_access_denies_inactive_user():
    db = Connection(active=False)
    policy = RolePolicy()
    policy.grant("viewer", "task:read")
    principal = Principal("user", "tenant-a", ("viewer",))
    assert not AccessService(db, policy).evaluate(
        principal, "task:read", resource_tenant_id="tenant-a"
    ).permitted
