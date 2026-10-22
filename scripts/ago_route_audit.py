"""Read-only audit of the ACTUAL localhost AGO server, not just Git files.

Use while the visual launcher is running. Refuse to claim success if the old
People & departments console or stale frontend is still being served.
"""
from __future__ import annotations

import argparse
import json
from urllib.error import HTTPError, URLError
from urllib.request import (
    build_opener, HTTPHandler, HTTPRedirectHandler, ProxyHandler, Request,
)

EXPECTED_MAP = "/workspace/organization/"
CHECKS = [
    ("/health/live", 200, None, '"status":"ok"'),
    ("/console", 308, EXPECTED_MAP, None),
    ("/console/", 308, EXPECTED_MAP, None),
    ("/console/assets/app.js", 404, None, None),
    ("/workspace/", 200, None, "Organization ID"),
    (EXPECTED_MAP, 200, None, "Work email"),
    ("/workspace/strategy/", 200, None, "Work email"),
    ("/workspace/governance/", 200, None, "Work email"),
    ("/workspace/knowledge/", 200, None, "Work email"),
    ("/workspace/tools/", 200, None, "Work email"),
    ("/workspace/calendar/", 200, None, "Work email"),
    ("/workspace/twin/", 200, None, "Work email"),
    ("/workspace/does-not-exist/", 404, None, None),
    ("/v1/console/me", 401, None, None),
]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def audit(port: int = 8000) -> dict:
    # No browser session, no Authorization/cookies, no writes, no remote origin.
    opener = build_opener(ProxyHandler({}), HTTPHandler(), NoRedirect())
    results = []
    for path, code, location, marker in CHECKS:
        observed = None
        body = ""
        redirected_to = None
        try:
            request = Request("http://127.0.0.1:" + str(port) + path,
                              headers={"Cache-Control": "no-cache"})
            try:
                response = opener.open(request, timeout=4)
            except HTTPError as e:
                response = e
            with response:
                observed = response.status
                redirected_to = response.headers.get("Location")
                body = response.read(262144).decode("utf-8", errors="replace")
        except (OSError, URLError, ValueError):
            pass
        ok = (
            observed == code
            and (location is None or redirected_to == location)
            and (marker is None or marker in body)
        )
        # If the old console responds 200, label the exact root cause.
        problem = None
        if not ok:
            if path in ("/console", "/console/") and observed == 200:
                problem = "OLD_CONSOLE_RUNNING_RESTART_OLD_SERVER"
            elif observed is None:
                problem = "NO_HTTP_RESPONSE_CHECK_PORT_AND_RUNNING_SERVER"
            else:
                problem = "UNEXPECTED_ROUTE_OR_STALE_BUILD"
        results.append({"route": path, "expected": code, "observed": observed,
                        "ok": ok, **({"problem": problem} if problem else {})})
    return {"overall": "PASS" if all(i["ok"] for i in results) else "FAIL",
            "checks": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("local port must be 1024-65535")
    result = audit(args.port)
    print(json.dumps(result, indent=2))
    return 0 if result["overall"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
