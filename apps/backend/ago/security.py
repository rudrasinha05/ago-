"""M1.5/M1.6 foundations: signed session tokens, password hashing, tenant RBAC.

This module deliberately has no user-registration or public login endpoint.
Identity persistence, revocation, MFA, and production key management remain separate.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from dataclasses import dataclass
from typing import Any


class AuthenticationError(ValueError):
    pass


class AuthorizationError(PermissionError):
    pass


def hash_password(password: str, *, iterations: int = 600_000) -> str:
    if len(password) < 12 or iterations < 100_000:
        raise ValueError("Password must have >=12 characters and sufficient work factor")
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"pbkdf2_sha256${iterations}${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(rounds)
        if not 100_000 <= iterations <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt), iterations
        )
        return hmac.compare_digest(digest, bytes.fromhex(expected))
    except (ValueError, TypeError):
        return False


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(data: str) -> bytes:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


@dataclass(frozen=True)
class Principal:
    subject: str
    tenant_id: str
    roles: tuple[str, ...]


class SessionTokens:
    """HMAC-SHA256 signed short-lived session tokens; not JWT/OIDC."""

    def __init__(self, secret: str, *, issuer: str = "ago", ttl_seconds: int = 900):
        if len(secret.encode()) < 32:
            raise ValueError("Signing secret must be at least 32 bytes")
        if not issuer or not 1 <= ttl_seconds <= 86_400:
            raise ValueError("Invalid issuer or TTL")
        self._secret = secret.encode()
        self.issuer = issuer
        self.ttl_seconds = ttl_seconds

    def issue(self, principal: Principal, *, now: int | None = None) -> str:
        if not principal.subject or not principal.tenant_id or not principal.roles:
            raise ValueError("Principal must have subject, tenant and roles")
        issued = int(time.time()) if now is None else now
        payload = {
            "iss": self.issuer, "sub": principal.subject, "tenant": principal.tenant_id,
            "roles": list(principal.roles), "iat": issued,
            "exp": issued + self.ttl_seconds, "nonce": secrets.token_hex(12),
        }
        body = _b64(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode())
        signature = _b64(hmac.new(self._secret, body.encode(), hashlib.sha256).digest())
        return f"{body}.{signature}"

    def verify(self, token: str, *, now: int | None = None) -> Principal:
        try:
            if len(token) > 4096:
                raise AuthenticationError("Invalid token")
            body, signature = token.split(".")
            expected = hmac.new(self._secret, body.encode(), hashlib.sha256).digest()
            if not hmac.compare_digest(expected, _unb64(signature)):
                raise AuthenticationError("Invalid token signature")
            data: dict[str, Any] = json.loads(_unb64(body))
            current = int(time.time()) if now is None else now
            if (
                data.get("iss") != self.issuer
                or type(data.get("iat")) is not int
                or type(data.get("exp")) is not int
                or not data["iat"] <= current < data["exp"]
                or data["exp"] - data["iat"] > self.ttl_seconds
                or not isinstance(data.get("sub"), str) or not data["sub"]
                or not isinstance(data.get("tenant"), str) or not data["tenant"]
                or not isinstance(data.get("roles"), list) or not data["roles"]
                or not all(isinstance(role, str) and role for role in data["roles"])
            ):
                raise AuthenticationError("Invalid or expired token")
            return Principal(data["sub"], data["tenant"], tuple(data["roles"]))
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError) as exc:
            raise AuthenticationError("Invalid token") from exc


class RolePolicy:
    """Deny-by-default RBAC. Tenant resource isolation is mandatory."""

    def __init__(self) -> None:
        self._grants: dict[str, set[str]] = {}

    def grant(self, role: str, permission: str) -> None:
        if not role or not permission:
            raise ValueError("Role and permission required")
        self._grants.setdefault(role, set()).add(permission)

    def revoke(self, role: str, permission: str) -> None:
        self._grants.get(role, set()).discard(permission)

    def allowed(self, principal: Principal, permission: str, *, tenant_id: str) -> bool:
        if not permission or not tenant_id or principal.tenant_id != tenant_id:
            return False
        return any(permission in self._grants.get(role, ()) for role in principal.roles)

    def require(self, principal: Principal, permission: str, *, tenant_id: str) -> None:
        if not self.allowed(principal, permission, tenant_id=tenant_id):
            raise AuthorizationError("Access denied")
