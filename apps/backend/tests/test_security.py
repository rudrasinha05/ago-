import pytest

from ago.security import (
    AuthenticationError, AuthorizationError, Principal, RolePolicy, SessionTokens,
    hash_password, verify_password,
)


def test_password_hash_and_verify():
    encoded = hash_password("very-long-password-123")
    assert verify_password("very-long-password-123", encoded)
    assert not verify_password("wrong-password", encoded)
    assert not verify_password("secret", "malformed")
    with pytest.raises(ValueError):
        hash_password("short")


def test_session_tokens_round_trip_and_expiry():
    tokens = SessionTokens("a" * 48, ttl_seconds=60)
    principal = Principal("user-1", "tenant-a", ("reader",))
    token = tokens.issue(principal, now=100)
    assert tokens.verify(token, now=101) == principal
    with pytest.raises(AuthenticationError):
        tokens.verify(token, now=160)
    with pytest.raises(AuthenticationError):
        tokens.verify(token + "x", now=101)
    with pytest.raises(AuthenticationError):
        SessionTokens("b" * 48).verify(token, now=101)


def test_session_tokens_reject_bad_configuration():
    with pytest.raises(ValueError):
        SessionTokens("short")
    with pytest.raises(ValueError):
        SessionTokens("a" * 32, ttl_seconds=0)


def test_tenant_scoped_rbac_deny_by_default():
    policy = RolePolicy()
    principal = Principal("user-1", "tenant-a", ("viewer",))
    assert not policy.allowed(principal, "tasks:read", tenant_id="tenant-a")
    policy.grant("viewer", "tasks:read")
    assert policy.allowed(principal, "tasks:read", tenant_id="tenant-a")
    assert not policy.allowed(principal, "tasks:read", tenant_id="tenant-b")
    with pytest.raises(AuthorizationError):
        policy.require(principal, "tasks:write", tenant_id="tenant-a")
    policy.revoke("viewer", "tasks:read")
    assert not policy.allowed(principal, "tasks:read", tenant_id="tenant-a")
