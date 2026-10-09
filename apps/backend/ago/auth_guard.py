"""Reusable FastAPI bearer-token and permission guards.

Trusted tenant IDs must come from server-side resource resolution, not request headers.
"""
from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Protocol

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ago.security import AuthenticationError, Principal, SessionTokens


class PermissionBackend(Protocol):
    def require(
        self, principal: Principal, permission: str, *, resource_tenant_id: str
    ) -> None: ...


_bearer = HTTPBearer(auto_error=False)


def bearer_principal(tokens: SessionTokens):
    def resolve(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None, Depends(_bearer)
        ],
    ) -> Principal:
        if credentials is None or credentials.scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            return tokens.verify(credentials.credentials)
        except AuthenticationError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

    return resolve


def permission_guard(
    tokens: SessionTokens,
    backend: PermissionBackend,
    permission: str,
    tenant_for_request: Callable[[Request], str],
):
    principal_dependency = bearer_principal(tokens)

    def guard(
        request: Request,
        principal: Annotated[Principal, Depends(principal_dependency)],
    ) -> Principal:
        tenant_id = tenant_for_request(request)
        try:
            backend.require(principal, permission, resource_tenant_id=tenant_id)
        except PermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            ) from exc
        return principal

    return guard
