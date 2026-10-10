"""Internal authentication API router with pluggable identity persistence.

Requires explicit application wiring and trusted tenant selection. Not mounted by default.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from ago.api_contracts import StrictInput
from ago.rate_limit import RateLimiter
from ago.security import Principal, SessionTokens


class IdentityBackend(Protocol):
    def authenticate(self, tenant_id: str, email: str, password: str) -> Principal | None: ...


class LoginRequest(StrictInput):
    tenant_id: str = Field(min_length=1, max_length=128)
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


@dataclass(frozen=True)
class AuthDependencies:
    identity: IdentityBackend
    tokens: SessionTokens
    tenant_validator: Callable[[str], bool]
    limiter: RateLimiter | None = None
    audit: Callable[[str, str], None] | None = None


def build_auth_router(dependencies: AuthDependencies) -> APIRouter:
    """Explicit opt-in. Production callers must add rate limits and audit logging."""
    router = APIRouter(prefix="/auth", tags=["authentication"])

    @router.post("/login", response_model=LoginResponse)
    def login(request: LoginRequest, http_request: Request) -> LoginResponse:
        if dependencies.limiter is not None:
            client = http_request.client.host if http_request.client else "unknown"
            if not dependencies.limiter.allow(client):
                raise HTTPException(status_code=429, detail="Too many attempts")
        if not dependencies.tenant_validator(request.tenant_id):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        principal = dependencies.identity.authenticate(
            request.tenant_id, request.email, request.password
        )
        if principal is None or not principal.roles:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
            )
        if dependencies.audit is not None:
            dependencies.audit("login", "success")
        return LoginResponse(
            access_token=dependencies.tokens.issue(principal),
            expires_in=dependencies.tokens.ttl_seconds,
        )

    return router
