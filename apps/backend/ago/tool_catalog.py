"""M8 fixed trusted enterprise tool catalog.

Exactly two internal read-only reports and one optional, operator-configured
HTTPS GET. Untrusted API/database values never turn into executable code or URLs.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
from collections.abc import Callable
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ago.scorecard import Scorecard


TOOL_DESCRIPTIONS = {
    "tool:scorecard": "Tenant-scoped operational scorecard (internal read-only)",
    "tool:knowledge_digest": "Verified/pending knowledge counts (internal read-only)",
    "tool:external_metrics": "Operator-selected HTTPS metrics GET (optional read-only)",
}
TOOL_CODES = frozenset(TOOL_DESCRIPTIONS)


def require_tool_code(code: str) -> str:
    if code not in TOOL_CODES:
        raise ValueError("Unregistered enterprise tool")
    return code


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise PermissionError("External tool redirects are not allowed")


class ReadOnlyMetricsProvider:
    """GET only a fixed endpoint at an operator-controlled public DNS hostname.

    JSON response is reduced to bounded numeric telemetry, preventing an
    accidental return of remote secrets or arbitrary provider text.
    DNS/network egress policy remains a separate production deployment gate.
    """

    def __init__(
        self, *, hostname: str, api_token: str,
        timeout: int = 5, opener: Callable | None = None,
    ):
        if not hostname or len(hostname) > 253 or not 1 <= timeout <= 10:
            raise ValueError("Invalid external metrics host or timeout")
        if not re.fullmatch(
            r"(?i)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
            r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)+",
            hostname,
        ):
            raise ValueError("External metrics hostname must be an FQDN")
        if hostname.lower().endswith((".local", ".internal", ".localhost", ".test")):
            raise ValueError("Private provider hostnames are prohibited")
        try:
            ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ValueError("IP literal endpoints are prohibited")
        if not api_token or "\n" in api_token or "\r" in api_token:
            raise ValueError("External metrics authentication token required")
        self.url = f"https://{hostname}/v1/metrics"
        self.token = api_token
        self.timeout = timeout
        self.opener = opener or build_opener(_NoRedirect()).open

    def fetch(self) -> dict:
        request = Request(
            self.url, method="GET",
            headers={
                "Authorization": "Bearer " + self.token,
                "Accept": "application/json",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                if response.status != 200:
                    raise RuntimeError("External metrics unavailable")
                raw = response.read(16_385)
        except (HTTPError, OSError) as exc:
            raise RuntimeError("External metrics unavailable") from exc
        if len(raw) > 16_384:
            raise ValueError("Provider response exceeds 16 KiB")
        document = json.loads(raw)
        if not isinstance(document, dict):
            raise ValueError("Metrics response must be a JSON object")
        values = document.get("metrics")
        if not isinstance(values, dict) or len(values) > 20:
            raise ValueError("Provider must return a bounded metrics object")
        import math

        metrics = {}
        for key, value in values.items():
            if (not isinstance(key, str) or not 1 <= len(key) <= 48
                    or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", key)
                    or type(value) not in (int, float)
                    or not math.isfinite(value)):
                raise ValueError("Provider metrics must be finite numeric telemetry")
            metrics[key] = value
        return {"source": "operator_https_readonly", "metrics": metrics,
                "untrusted_external_data": True}


def handlers(db) -> dict[str, Callable]:
    """Explicit static mapping. No arbitrary provider code can be registered."""

    def scorecard(task):
        return {
            "kind": "tenant_scorecard", "task_id": task.id,
            "data": Scorecard(db).summary(tenant_id=task.tenant_id),
            "requires_human_qa": True,
        }

    def knowledge(task):
        row = db.execute(
            """SELECT count(*) FILTER (WHERE status='verified') AS verified,
                      count(*) FILTER (WHERE status='pending') AS pending
               FROM ago_knowledge_nodes WHERE tenant_id=%s""",
            (task.tenant_id,),
        ).fetchone()
        return {
            "kind": "knowledge_digest", "task_id": task.id,
            "verified": int(row["verified"]), "pending": int(row["pending"]),
            "requires_human_qa": True,
        }

    def external(task):
        if os.getenv("AGO_M8_EXTERNAL_ENABLED") != "true":
            raise PermissionError("External metrics explicitly disabled by operator")
        provider = ReadOnlyMetricsProvider(
            hostname=os.getenv("AGO_M8_METRICS_HOST", ""),
            api_token=os.getenv("AGO_M8_METRICS_TOKEN", ""),
        )
        return {
            "kind": "external_metrics", "task_id": task.id,
            "data": provider.fetch(), "requires_human_qa": True,
        }

    return {
        "tool:scorecard": scorecard,
        "tool:knowledge_digest": knowledge,
        "tool:external_metrics": external,
    }
