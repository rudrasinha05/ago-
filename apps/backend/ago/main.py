"""AGO API entry point."""
from __future__ import annotations

import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ago.api_agents import router as agents_router
from ago.api_insights import router as insights_router
from ago.api_brain import router as brain_router
from ago.api_m2 import router as m2_router
from ago.api_meta import router as meta_router
from ago.api_operations import router as operations_router
from ago.api_knowledge import router as knowledge_router
from ago.api_council import router as council_router
from ago.platform import Settings, build_container, configure_logging, request_id
from ago.readiness import ReadinessChecks


def postgres_available() -> bool:
    """Verify configured PostgreSQL responds; no DSN means not ready."""
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        return False
    import psycopg

    with psycopg.connect(dsn, connect_timeout=3) as connection:
        return connection.execute("SELECT 1").fetchone()[0] == 1


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings)
    app = FastAPI(title="Artificial General Organization", version="0.1.0")
    app.state.container = build_container(settings)
    checks = ReadinessChecks()
    checks.register("postgres", postgres_available)
    app.state.readiness_checks = checks
    app.include_router(m2_router)
    app.include_router(brain_router)
    app.include_router(agents_router)
    app.include_router(insights_router)
    app.include_router(operations_router)
    app.include_router(knowledge_router)
    app.include_router(council_router)
    app.include_router(meta_router)

    try:
        import psycopg

        @app.exception_handler(psycopg.IntegrityError)
        async def database_conflict(_request: Request, _exc: psycopg.IntegrityError):
            return JSONResponse(status_code=409, content={"detail": "Database conflict"})
    except ImportError:
        pass

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        correlation_id = incoming if incoming and len(incoming) <= 128 else str(uuid4())
        token = request_id.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation_id
            return response
        finally:
            request_id.reset(token)

    @app.get("/health/live")
    def liveness() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/health/ready")
    def readiness():
        results = checks.run()
        ready = bool(results) and all(result.healthy for result in results)
        return JSONResponse(
            status_code=200 if ready else 503,
            content={
                "status": "ready" if ready else "not_ready",
                "checks": {
                    result.name: {"healthy": result.healthy, "detail": result.detail}
                    for result in results
                },
            },
        )

    return app


app = create_app()
