"""Founder-only localhost export of a REAL persisted AGO AI engineering run.

Read-only preview by default. An explicit opt-in writes a new validated
candidate receipt for the existing offline Docker -> QA delivery flow.
No inference, GitHub API calls, remote execution, auto-approval or release.
"""
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import UUID

from ago.company_engineering import verify_persisted_candidate
from local_approved_agent_batch import founder_login, local_url

CONFIRM = "EXPORT_APPROVED_AI_CANDIDATE"
BOARD_SEATS = (
    "Strategy & Vision", "Technology Oversight", "Finance & Budget",
    "Risk & Compliance", "Quality & Release",
)
ROLE_ORDER = ("ceo", "cto", "finance", "risk", "quality", "pm", "employee")
MAX_HTTP_BYTES = 4_000_000


def choose_run(runs: list, run_id: str) -> dict:
    """Only the exact completed run with all real Board evidence is exportable."""
    wanted = str(UUID(run_id))
    if not isinstance(runs, list) or len(runs) > 100:
        raise ValueError("Expected bounded authenticated AGO runs")
    matches = [row for row in runs
               if isinstance(row, dict) and row.get("id") == wanted]
    if len(matches) != 1:
        raise PermissionError("One exact persisted agent run must be selected")
    row = matches[0]
    if row.get("status") != "completed":
        raise PermissionError("An incomplete or failed run cannot be exported")
    task_id = str(UUID(str(row["task_id"])))
    result = row.get("result")
    if not isinstance(result, dict) or (
        result.get("kind") != "local_company_governed_handoff"
        or result.get("project_released") is not False
        or result.get("github_commits_created") is not False
        or result.get("board_review_mode") != "full_five_seat"
        or result.get("board_review_cleared") is not True
        or result.get("board_blocked") is not False
        or result.get("handoff_complete") is not True
        or result.get("roles_expected") != 7
        or result.get("roles_completed") != 7
        or result.get("engineering_candidate_status") != "syntax_reviewed"
        or result.get("requires_human_qa") is not True
        or result.get("task_id") != task_id
    ):
        raise PermissionError("A complete cleared Board and real engineering run are required")
    project_id = str(UUID(str(result["project_id"])))
    votes = result.get("board_recommendations")
    handoffs = result.get("handoffs")
    if not isinstance(votes, list) or len(votes) != 5:
        raise PermissionError("Five verified independent AI Board recommendations required")
    if (not isinstance(handoffs, list) or len(handoffs) != 7
            or [h.get("role") for h in handoffs if isinstance(h, dict)]
            != list(ROLE_ORDER)):
        raise PermissionError("Seven ordered AI role handoffs required")
    employees = [h.get("employee_id") for h in handoffs]
    if (any(not isinstance(x, str) or not x for x in employees)
            or len(set(employees)) != 7):
        raise PermissionError("Distinct source-backed AI employees required")
    for i, (seat, vote) in enumerate(zip(BOARD_SEATS, votes, strict=True)):
        if (not isinstance(vote, dict) or vote.get("seat") != seat
                or vote.get("employee_id") != employees[i]
                or vote.get("recommendation") != "approve"
                or vote.get("verifiable_model_output") is not True
                or vote.get("binding_authorization") is not False):
            raise PermissionError("One or more Board recommendations cannot be verified")
    candidate = verify_persisted_candidate(result.get("engineering_candidate"))
    # Strip arbitrary model prose, private project brief, DNA and credentials.
    # Only bytes required by the existing approved Board receipt parser survive.
    return {
        "id": wanted, "task_id": task_id, "project_id": project_id,
        "status": "completed", "source": "ago_authenticated_founder_run",
        "result": {
            "board_review_cleared": True,
            "engineering_candidate": candidate,
        },
    }


def _request_json(base: str, token: str, endpoint: str, *, opener=urlopen):
    if not isinstance(token, str) or not token or len(token) > 4096 or any(
        char in token for char in "\r\n"
    ):
        raise PermissionError("Invalid local AGO session")
    if endpoint not in ("/v1/console/me", "/v1/agents/runs"):
        raise PermissionError("Only authenticated read endpoints supported")
    req = Request(local_url(base) + endpoint, method="GET",
                  headers={"Authorization": "Bearer " + token,
                           "Accept": "application/json"})
    with opener(req, timeout=15) as response:
        data = response.read(MAX_HTTP_BYTES + 1)
    if len(data) > MAX_HTTP_BYTES:
        raise ValueError("AGO run response exceeds local read budget")
    return json.loads(data)


def export_from_founder_session(base: str, token: str, run_id: str, output: Path,
                                *, apply=False, confirm="", opener=urlopen) -> dict:
    base = local_url(base)
    me = _request_json(base, token, "/v1/console/me", opener=opener)
    if not isinstance(me, dict) or "founder" not in me.get("roles", []):
        raise PermissionError("An authenticated Founder role is required")
    runs = _request_json(base, token, "/v1/agents/runs", opener=opener)
    selected = choose_run(runs, run_id)
    candidate = selected["result"]["engineering_candidate"]
    summary = {
        "mode": "preview" if not apply else "exported_for_offline_source_review",
        "run_id": selected["id"], "task_id": selected["task_id"],
        "project_id": selected["project_id"],
        "candidate_sha256": candidate["candidate_sha256"],
        "file_count": len(candidate["files"]),
        "tests_executed": False,
        "independent_qa_approved": False,
        "github_committed": False, "release_ready": False,
    }
    if not apply:
        return summary
    if confirm != CONFIRM:
        raise PermissionError("Separate Founder export authorization required")
    if output.exists() or output.is_symlink() or not output.parent.is_dir():
        raise FileExistsError("Export requires a new file in an existing directory")
    # Explicit local-only write; exclusive creation prevents overwrite/replay.
    # This receipt remains UNTESTED and UNAPPROVED.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(selected, stream, indent=2, sort_keys=True)
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        if args.apply and args.confirm != CONFIRM:
            raise PermissionError("Exact Founder confirmation required")
        base = local_url(args.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder work email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password)
        del password
        result = export_from_founder_session(
            base, token, args.run_id, args.output,
            apply=args.apply, confirm=args.confirm,
        )
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "exported": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        # No private brief, token, candidate body, raw server text or traceback.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "exported": False, "release_ready": False}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
