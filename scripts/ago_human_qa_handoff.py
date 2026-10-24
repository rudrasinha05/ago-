"""Link a locally tested AGO AI candidate to real independent human task QA.

This is a bounded, authenticated localhost review operation, not automated QA.
Preview checks exact source/run/Docker receipts and server QA queue. Confirmed
apply writes one durable no-replay attempt BEFORE an authenticated review POST.
No external GitHub operation, model use or release occurs here.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path
from urllib.request import ProxyHandler, Request, build_opener
from uuid import UUID

from ago.model_provider import _DenyRedirect

from ago_engineering_candidate import inspect as inspect_run
from ago_qa_review_packet import packet
from local_approved_agent_batch import DurableAttemptJournal, founder_login, local_url

CONFIRM = "INDEPENDENT_HUMAN_QA_DECISION"
MAX_JSON = 20000
LOCAL_OPENER = build_opener(ProxyHandler({}), _DenyRedirect()).open


def read_document(path: Path, *, max_bytes: int = MAX_JSON) -> dict:
    if (not path.is_file() or path.is_symlink()
            or path.stat().st_size > max_bytes):
        raise ValueError("A small regular local evidence file is required")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict):
        raise TypeError("Local evidence must be one JSON object")
    return result


def verify_handoff(export: Path, staged: Path, qa_file: Path) -> dict:
    """Never accept a claimed QA result without recomputing its local evidence."""
    source = read_document(export, max_bytes=40000)
    if (source.get("source") != "ago_authenticated_founder_run"
            or source.get("status") != "completed"
            or not isinstance(source.get("result"), dict)
            or source["result"].get("board_review_cleared") is not True):
        raise PermissionError("Exact completed Board-cleared AGO source required")
    run_id = str(UUID(str(source["id"])))
    task_id = str(UUID(str(source["task_id"])))
    project_id = str(UUID(str(source["project_id"])))
    candidate = inspect_run(export)
    fresh = packet(staged)
    saved = read_document(qa_file)
    if (saved != fresh or saved.get("candidate_sha256") != candidate["candidate_sha256"]
            or fresh["independent_human_qa_pending"] is not True
            or fresh["qa_approved"] is not False
            or fresh["github_write_authorized"] is not False
            or fresh["release_ready"] is not False):
        raise PermissionError("Exact matching pending QA packet and tested source required")
    return {
        "run_id": run_id, "task_id": task_id, "project_id": project_id,
        "candidate_sha256": candidate["candidate_sha256"],
        "test_receipt_sha256": fresh["local_test_receipt_sha256"],
        "unittest_cases": fresh["unittest_cases"],
    }


def remote_json(base: str, token: str, endpoint: str, *,
                method: str = "GET", payload=None, opener=LOCAL_OPENER) -> object:
    allowed = (
        endpoint in ("/v1/console/me", "/v1/console/qa-queue")
        and method == "GET"
    ) or (
        endpoint.startswith("/v1/tasks/")
        and re.fullmatch(r"/v1/tasks/[0-9a-f-]{36}/review", endpoint)
        and method in ("GET", "POST")
    )
    if not allowed or not isinstance(token, str) or not token or len(token) > 4096:
        raise PermissionError("Authenticated exact AGO review endpoint required")
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = Request(local_url(base) + endpoint, data=data, method=method,
                  headers={"Authorization": "Bearer " + token,
                           "Accept": "application/json",
                           "Content-Type": "application/json"})
    with opener(req, timeout=15) as response:
        raw = response.read(MAX_JSON + 1)
    if len(raw) > MAX_JSON:
        raise ValueError("Local API response exceeds bounded review limit")
    return json.loads(raw)


def review_from_session(
    base: str, token: str, export: Path, staged: Path, qa_file: Path,
    *, verdict: str, notes: str, apply=False, confirm="",
    journal: DurableAttemptJournal | None = None, opener=LOCAL_OPENER,
) -> dict:
    evidence = verify_handoff(export, staged, qa_file)
    if verdict not in ("pass", "fail") or not isinstance(notes, str) or not 15 <= len(notes.strip()) <= 1200:
        raise ValueError("Independent QA requires an explicit verdict and substantive notes")
    me = remote_json(base, token, "/v1/console/me", opener=opener)
    if (not isinstance(me, dict) or not isinstance(me.get("id"), str)
            or "qa:review" not in me.get("permissions", [])
            or "qa:read" not in me.get("permissions", [])):
        raise PermissionError("An authenticated independent human QA reviewer is required")
    queue = remote_json(base, token, "/v1/console/qa-queue", opener=opener)
    if not isinstance(queue, list):
        raise TypeError("Server QA queue evidence must be a list")
    matches = [x for x in queue if isinstance(x, dict)
               and str(x.get("id")) == evidence["task_id"]]
    if (len(matches) != 1 or matches[0].get("status") != "completed"
            or str(matches[0].get("assignee_id")) == me["id"]):
        raise PermissionError("Exact completed, unreviewed task assigned to another employee required")
    summary = {
        **evidence, "verdict": verdict,
        "reviewer_id": me["id"],
        "mode": "review_preview" if not apply else "review_submitted",
        "independent_human_qa_recorded": False,
        "github_write_authorized": False, "release_ready": False,
    }
    if not apply:
        return summary
    if confirm != CONFIRM:
        raise PermissionError("Separate human reviewer confirmation required")
    if journal is None:
        raise PermissionError("Durable no-replay review attempt journal required")
    # The journal protects uncertain POST outcomes (including network timeout)
    # across restarts; an earlier review cannot be silently submitted again.
    if not journal.claim(evidence["task_id"]):
        raise FileExistsError("Review POST previously attempted; inspect AGO before retry")
    message = (
        "AGO independent human QA; "
        "run=" + evidence["run_id"] + "; "
        "project=" + evidence["project_id"] + "; "
        "candidate_sha256=" + evidence["candidate_sha256"] + "; "
        "docker_receipt_sha256=" + evidence["test_receipt_sha256"] + "; "
        "tests=" + str(evidence["unittest_cases"]) + "; "
        "reviewer_notes=" + notes.strip()
    )
    recorded = remote_json(
        base, token, "/v1/tasks/" + evidence["task_id"] + "/review",
        method="POST", payload={"verdict": verdict, "evidence": message},
        opener=opener,
    )
    if (not isinstance(recorded, dict)
            or str(recorded.get("artifact_id")) != evidence["task_id"]
            or str(recorded.get("reviewer_id")) != me["id"]
            or recorded.get("verdict") != verdict
            or recorded.get("evidence") != message):
        raise PermissionError("AGO did not confirm an exact matching human QA record")
    summary["independent_human_qa_recorded"] = True
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--export", required=True, type=Path)
    parser.add_argument("--staged-directory", required=True, type=Path)
    parser.add_argument("--qa-packet", required=True, type=Path)
    parser.add_argument("--verdict", choices=("pass", "fail"), required=True)
    parser.add_argument("--notes", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--attempt-journal", type=Path,
                        default=Path.home() / ".ago" / "human_qa_attempts")
    a = parser.parse_args(argv)
    try:
        if a.apply and a.confirm != CONFIRM:
            raise PermissionError("Exact human QA confirmation required")
        base = local_url(a.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Independent human QA reviewer email: ").strip()
        password = getpass.getpass("Human reviewer password (hidden): ")
        token = founder_login(base, tenant, email, password, opener=LOCAL_OPENER)
        del password
        result = review_from_session(
            base, token, a.export, a.staged_directory, a.qa_packet,
            verdict=a.verdict, notes=a.notes, apply=a.apply, confirm=a.confirm,
            journal=DurableAttemptJournal(a.attempt_journal) if a.apply else None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "qa_approved": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        # Never echo credentials, untrusted server payloads or private source.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "github_write_authorized": False, "release_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
