"""Serve only the packaged Next.js Company Map on the existing API origin.

The retired M9 console bundle is no longer mounted or shipped. Old /console
bookmarks redirect to the single Company Map; no feature flag can restore it.
"""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

FRONTEND = Path(__file__).resolve().parent / "frontend"
COMPANY_MAP = "/workspace/organization/"


def register_console(app: FastAPI) -> None:
    """Install one static shell; all private /v1 data remains authorized."""
    if (FRONTEND / "index.html").is_file():
        app.mount("/workspace", StaticFiles(directory=FRONTEND, html=True), name="workspace")

    @app.get("/console", include_in_schema=False)
    @app.get("/console/", include_in_schema=False)
    def redirect_retired_console():
        return RedirectResponse(url=COMPANY_MAP, status_code=308)


def console_headers(path: str) -> dict[str, str]:
    is_workspace = path == "/workspace" or path.startswith("/workspace/")
    if not (is_workspace or path == "/console" or path.startswith("/console/")):
        return {}
    hashes = []
    if is_workspace:
        hashes_file = FRONTEND / "csp.json"
        hashes = json.loads(hashes_file.read_text()) if hashes_file.is_file() else []
    return {
        "Content-Security-Policy": (
            "default-src 'none'; script-src 'self' " + " ".join(hashes) + "; "
            "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
            "connect-src 'self'; font-src 'self'; object-src 'none'; "
            "base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
        ),
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cache-Control": "no-store, private",
        "Cross-Origin-Resource-Policy": "same-origin",
    }
