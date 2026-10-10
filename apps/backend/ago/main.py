"""AGO API entry point."""

from __future__ import annotations

import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ago.api_agents import router as agents_router
from ago.api_brain import router as brain_router
from ago.api_council import router as council_router
from ago.api_insights import router as insights_router
from ago.api_knowledge import router as knowledge_router
from ago.api_m2 import router as m2_router
from ago.api_meta import router as meta_router
from ago.api_operations import router as operations_router
from ago.api_tools import router as tools_router
from ago.console_api import router as console_router
from ago.console_host import console_headers, register_console
from ago.http_errors import correlation_id, install_error_handlers
from ago.platform import Settings, build_container, configure_logging, request_id
from ago.readiness import ReadinessChecks
from ago.release_security import ReleasePolicy, install_release_perimeter, schema_integrity
from ago.security_material import bootstrap_security


def postgres_available() -> bool:
    """Verify configured PostgreSQL responds; no DSN means not ready."""
    dsn = os.getenv("AGO_POSTGRES_DSN")
    if not dsn:
        return False
    import psycopg

    with psycopg.connect(dsn, connect_timeout=3) as connection:
        return connection.execute("SELECT 1").fetchone()[0] == 1


def create_app() -> FastAPI:
    bootstrap_security()
    settings = Settings()
    policy = ReleasePolicy.from_environment(settings.environment)
    configure_logging(settings)
    app = FastAPI(
        title="Artificial General Organization",
        version="0.1.0",
        docs_url=None if policy.production else "/docs",
        redoc_url=None if policy.production else "/redoc",
        openapi_url=None if policy.production else "/openapi.json",
    )
    app.state.container = build_container(settings)
    checks = ReadinessChecks()
    checks.register("postgres", postgres_available)
    if policy.production:
        checks.register("migrations", lambda: schema_integrity(os.environ["AGO_POSTGRES_DSN"]))
    app.state.readiness_checks = checks
    app.include_router(m2_router)
    app.include_router(brain_router)
    app.include_router(agents_router)
    app.include_router(insights_router)
    app.include_router(operations_router)
    app.include_router(knowledge_router)
    app.include_router(council_router)
    app.include_router(meta_router)
    app.include_router(tools_router)
    app.include_router(console_router)
    register_console(app)

    install_error_handlers(app)

    @app.middleware("http")
    async def correlate(request: Request, call_next):
        incoming = request.headers.get("x-request-id")
        correlation = correlation_id(incoming)
        request.state.request_id = correlation
        token = request_id.set(correlation)
        try:
            response = await call_next(request)
            response.headers["x-request-id"] = correlation
            for key, value in console_headers(request.url.path).items():
                response.headers[key] = value
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

    install_release_perimeter(app, policy)
    return app


app = create_app()
