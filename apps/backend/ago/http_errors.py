"""Uniform business/HTTP errors; validation never echoes submitted values."""

from __future__ import annotations

from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

ERROR_CODES = {
    400: "invalid_request",
    401: "authentication_required",
    403: "permission_denied",
    404: "not_found",
    409: "conflict",
    413: "request_too_large",
    422: "validation_failed",
    426: "https_required",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_failed",
    503: "unavailable",
}


def correlation_id(incoming: str | None) -> str:
    if (
        incoming
        and len(incoming) <= 128
        and incoming.isascii()
        and incoming.isprintable()
        and "\\r" not in incoming
        and "\\n" not in incoming
    ):
        return incoming
    return str(uuid4())


def error_response(status: int, detail, *, request_id: str, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "detail": detail,
            "error": {"code": ERROR_CODES.get(status, "http_error"), "request_id": request_id},
        },
        headers={**(headers or {}), "x-request-id": request_id},
    )


def install_error_handlers(app: FastAPI) -> None:
    def rid(request: Request) -> str:
        return getattr(request.state, "request_id", None) or correlation_id(
            request.headers.get("x-request-id")
        )

    async def http(request: Request, exc: HTTPException):
        return error_response(
            exc.status_code, exc.detail, request_id=rid(request), headers=exc.headers
        )

    async def validation(request: Request, exc: RequestValidationError):
        # Pydantic input/ctx may contain credentials or untrusted exception objects.
        safe = [
            {"loc": e["loc"], "type": e["type"], "msg": "Invalid request value"}
            for e in exc.errors()
        ]
        return error_response(422, safe, request_id=rid(request))

    async def business(request: Request, exc: Exception):
        status = (
            403
            if isinstance(exc, PermissionError)
            else (404 if isinstance(exc, LookupError) else 400)
        )
        detail = {400: "Invalid request", 403: "Permission denied", 404: "Resource not found"}[
            status
        ]
        return error_response(status, detail, request_id=rid(request))

    async def unexpected(request: Request, _exc: Exception):
        return error_response(500, "Internal server error", request_id=rid(request))

    app.add_exception_handler(HTTPException, http)
    app.add_exception_handler(RequestValidationError, validation)
    for kind in (PermissionError, LookupError, ValueError):
        app.add_exception_handler(kind, business)
    app.add_exception_handler(Exception, unexpected)
    try:
        import psycopg

        async def conflict(request: Request, _exc: psycopg.IntegrityError):
            return error_response(409, "Database conflict", request_id=rid(request))

        app.add_exception_handler(psycopg.IntegrityError, conflict)
    except ImportError:
        pass
