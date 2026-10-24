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
        return Cursor(None if "ago_constitution_adoptions" in query else ({"ok": True} if self.found else None))


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


def test_security_audit_never_persists_arbitrary_secret_payloads():
    import json

    db = DB()
    payload = {
        "reason": "bad_credentials",
        "context": "tools",
        "source": "constitution",
        "password": "SUPER_PRIVATE_TEST_PASSWORD",
        "api_token": "SUPER_PRIVATE_TEST_TOKEN",
        "founder_brief": "SUPER_PRIVATE_TEST_IDEA",
        "prompt": "SUPER_PRIVATE_TEST_PROMPT",
        "email": "founder_private@example.org",
        "traceback": "Traceback SUPER_PRIVATE_TEST_STACK",
        "record_id": "f63ea5c0-207f-41f5-bdc8-00b1cbeae79c",
        "details": {"deep": ["SUPER_PRIVATE_TEST_NESTED"]},
        "category": "handler_failed SUPER_PRIVATE_TEST_EXCEPTION",
    }
    SecurityControls(db).audit("tool:denied", "blocked", tenant_id="tenant-a",
                               actor_id="worker-a", metadata=payload)
    metadata = db.calls[-1][1][-1]
    parsed = json.loads(metadata)
    assert parsed["reason"] == "bad_credentials"
    assert parsed["context"] == "tools"
    assert parsed["record_id"] == payload["record_id"]
    for secret in ("SUPER_PRIVATE_TEST_PASSWORD", "SUPER_PRIVATE_TEST_TOKEN",
                   "SUPER_PRIVATE_TEST_IDEA", "SUPER_PRIVATE_TEST_PROMPT",
                   "founder_private@example.org", "SUPER_PRIVATE_TEST_STACK",
                   "SUPER_PRIVATE_TEST_NESTED", "SUPER_PRIVATE_TEST_EXCEPTION"):
        assert secret not in metadata
    assert "password" not in parsed and "founder_brief" not in parsed
    assert "traceback" not in parsed and "details" not in parsed
    assert parsed["category"] == "[redacted]"


def test_security_audit_redaction_will_not_stringify_untrusted_object():
    import json

    class Hostile:
        def __str__(self):
            raise AssertionError("Untrusted audit object stringified")

        def __repr__(self):
            raise AssertionError("Untrusted audit object repr leaked")

    db = DB()
    SecurityControls(db).audit("read", "denied", metadata={
        "reason": Hostile(), "private": Hostile(),
        "context": ["SUPER_PRIVATE_TEST_LIST"],
    })
    parsed = json.loads(db.calls[-1][1][-1])
    assert parsed == {"reason": "[redacted]", "context": "[redacted]"}
