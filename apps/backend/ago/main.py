"""AGO API entry point."""
from fastapi import FastAPI, Request
from uuid import uuid4

from ago.platform import Settings, build_container, configure_logging, request_id


def create_app() -> FastAPI:
    settings = Settings()
    configure_logging(settings)
    app = FastAPI(title="Artificial General Organization", version="0.1.0")
    app.state.container = build_container(settings)

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
    def readiness() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
