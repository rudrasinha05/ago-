"""Login security edge-condition tests."""
import pytest

from ago.login_security import LoginThrottle
from ago.provision import add_reviewer


def test_throttle_rejects_too_low_threshold():
    with pytest.raises(ValueError):
        LoginThrottle(None, max_attempts=1)


def test_reviewer_tenant_id_required():
    with pytest.raises(ValueError):
        add_reviewer(None, tenant_id="not-a-uuid", email="reviewer@example.test", password="long-password")


class Cursor:
    def __init__(self, row):
        self.row = row

    def fetchone(self):
        return self.row


class Fake:
    def __init__(self):
        self.queries = []

    def execute(self, sql, params):
        self.queries.append((sql, params))
        if "FROM ago_tenants" in sql:
            return Cursor({"exists": True})
        if "FOR UPDATE" in sql:
            return Cursor({"failures": 0, "blocked": False})
        return Cursor(None)


def test_login_throttle_normalizes_case():
    db = Fake()
    security = LoginThrottle(db)
    assert security.begin("t", " User@Example.com ")
    security.failure("t", " User@Example.com ")
    assert db.queries[-1][1][-1] == "user@example.com"
    security.success("t", " User@Example.com ")
    assert db.queries[-1][1][-1] == "user@example.com"
