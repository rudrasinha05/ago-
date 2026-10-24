"""Submit exact QA-verified GitHub commit draft to AGO governance (NOT GitHub).

Revalidates source, human QA and immutable operation before a single,
durably claimed localhost proposal POST. Separate independent enterprise
approval, application, GitHub execution and PR remain mandatory.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from urllib.request import Request
from uuid import UUID

from ago.company_engineering import draft_github_commit_operation
from ago_engineering_candidate import inspect as inspect_run
from ago_human_qa_handoff import LOCAL_OPENER, read_document
from ago_prepare_github_handoff import verified_qa
from local_approved_agent_batch import DurableAttemptJournal, founder_login, local_url

CONFIRM = "SUBMIT_QA_VERIFIED_GITHUB_PROPOSAL"


def inspect_verified_draft(draft: Path, source: Path, stage: Path, qa_file: Path,
                           *, base: str, token: str, opener=LOCAL_OPENER) -> dict:
    row = read_document(draft, max_bytes=65000)
    proof = verified_qa(source, stage, qa_file, base=base, token=token, opener=opener)
    if (row.get("kind") != "ago_human_qa_verified_github_draft"
            or row.get("origin_run_id") != proof["run_id"]
            or row.get("origin_task_id") != proof["task_id"]
            or row.get("origin_project_id") != proof["project_id"]
            or row.get("candidate_sha256") != proof["candidate_sha256"]
            or row.get("docker_receipt_sha256") != proof["test_receipt_sha256"]
            or row.get("human_qa_reviewer_id") != proof["qa_reviewer_id"]
            or row.get("human_qa_verdict") != "pass"
            or row.get("independent_human_qa_verified") is not True
            or row.get("github_write_authorized") is not False
            or row.get("operation_submitted_to_ago") is not False
            or row.get("github_committed") is not False
            or row.get("release_ready") is not False):
        raise PermissionError("Exact previously QA-verified unsubmitted draft required")
    operation = row.get("github_operation")
    if not isinstance(operation, dict) or operation.get("operation") != "commit_files":
        raise PermissionError("Only an unsubmitted bounded commit_files operation is supported")
    payload = operation.get("payload")
    if not isinstance(payload, dict):
        raise TypeError("GitHub operation must have exact typed payload")
    exact = draft_github_commit_operation(
        inspect_run(source), project_id=operation["project_id"],
        operation_id=operation["id"], expected_sha=payload["expected_sha"],
        message=payload["message"],
    )
    if (exact != operation
            or row.get("github_project_id") != operation["project_id"]
            or row.get("founder_reviewed_expected_sha") != payload["expected_sha"]):
        raise PermissionError("Reviewed source or GitHub operation was changed")
    return {"operation": operation, "qa": proof}


def enterprise_call(base: str, token: str, *, method: str, body=None,
                    opener=LOCAL_OPENER):
    if method not in ("GET", "POST"):
        raise ValueError("Read or single proposal submit only")
    path = "/v1/enterprise/reviews/integration"
    if method == "POST":
        path += "/propose"
    if not isinstance(token, str) or not token or len(token) > 4096:
        raise PermissionError("Signed Founder session required")
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        local_url(base) + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json",
                 "Content-Type": "application/json"},
    )
    with opener(req, timeout=20) as response:
        raw = response.read(65537)
    if len(raw) > 65536:
        raise ValueError("AGO enterprise response exceeds limit")
    return json.loads(raw)


def submit(
    draft: Path, source: Path, stage: Path, qa_file: Path,
    *, base: str, token: str, apply=False, confirm="",
    journal: DurableAttemptJournal | None = None, opener=LOCAL_OPENER,
):
    checked = inspect_verified_draft(
        draft, source, stage, qa_file, base=base, token=token, opener=opener,
    )
    latest = enterprise_call(base, token, method="GET", opener=opener)
    revision = latest.get("revision") if isinstance(latest, dict) else None
    if type(revision) is not int or revision < 0:
        raise TypeError("Exact live enterprise integration revision required")
    op = checked["operation"]
    evidence = checked["qa"]
    summary = {
        "kind": "ago_governed_github_proposal",
        "operation_id": op["id"], "github_project_id": op["project_id"],
        "candidate_sha256": evidence["candidate_sha256"],
        "qa_reviewer_id": evidence["qa_reviewer_id"],
        "integration_revision": revision,
        "mode": "preview" if not apply else "proposal_submitted_for_independent_review",
        "github_network_called": False,
        "github_committed": False, "approved": False, "release_ready": False,
    }
    if not apply:
        return summary
    if confirm != CONFIRM or journal is None:
        raise PermissionError("Explicit Founder consent and durable no-replay required")
    operation_key = op["id"]
    if not journal.claim(operation_key):
        raise FileExistsError("Prior proposal POST may have succeeded; inspect AGO")
    payload = {
        "command": "github_operation", "specification": op,
        "operation_key": operation_key, "base_revision": revision,
        "rationale": (
            "Founder submits human-QA-verified candidate "
            + evidence["candidate_sha256"]
            + " from signed QA reviewer " + evidence["qa_reviewer_id"]
            + " and offline test receipt " + evidence["test_receipt_sha256"]
            + ". Independent governance approval is still mandatory."
        ),
    }
    result = enterprise_call(base, token, method="POST", body=payload, opener=opener)
    if (not isinstance(result, dict)
            or result.get("command") != "github_operation"
            or result.get("operation_key") != operation_key):
        raise PermissionError("AGO did not confirm exact immutable GitHub proposal")
    summary["proposal_id"] = str(result["id"])
    summary["review_approval_id"] = str(UUID(str(result["approval_id"])))
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--local-url", default="http://127.0.0.1:8000")
    for name in ("draft", "export", "staged-directory", "qa-packet"):
        p.add_argument("--" + name, type=Path, required=True)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm", default="")
    p.add_argument("--attempt-journal", type=Path,
                   default=Path.home() / ".ago" / "github_proposal_attempts")
    a = p.parse_args(argv)
    try:
        if a.apply and a.confirm != CONFIRM:
            raise PermissionError("Exact Founder approval required")
        base = local_url(a.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password, opener=LOCAL_OPENER)
        del password
        result = submit(
            a.draft, a.export, a.staged_directory, a.qa_packet,
            base=base, token=token, apply=a.apply, confirm=a.confirm,
            journal=DurableAttemptJournal(a.attempt_journal) if a.apply else None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "github_committed": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "github_committed": False, "release_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
