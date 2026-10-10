"""Serve the first-party M9 organizational console on the existing API origin.

The console is public static shell code; all business data is served exclusively
by existing signed-session and tenant-RBAC-protected /v1 APIs.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

ASSETS = Path(__file__).resolve().parent / "console"
CONSOLE_CSP = (
    "default-src 'none'; script-src 'self'; style-src 'self'; "
    "img-src 'self' data:; connect-src 'self'; font-src 'self'; "
    "object-src 'none'; base-uri 'none'; form-action 'self'; "
    "frame-ancestors 'none'"
)


def register_console(app: FastAPI) -> None:
    """Install same-origin static assets with no third-party dependencies."""
    app.mount(
        "/console/assets",
        StaticFiles(directory=ASSETS, check_dir=True),
        name="console-assets",
    )

    @app.get("/console", include_in_schema=False)
    def redirect_console():
        return RedirectResponse(url="/console/", status_code=308)

    @app.get("/console/", include_in_schema=False)
    def console_home():
        return FileResponse(ASSETS / "index.html", media_type="text/html")


def console_headers(path: str) -> dict[str, str]:
    if not (path == "/console" or path.startswith("/console/")):
        return {}
    return {
        "Content-Security-Policy": CONSOLE_CSP,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store, private",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
