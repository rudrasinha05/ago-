"""Prepare only a source- and human-QA-backed, UNEXECUTED GitHub draft.

An authenticated Founder must verify a persisted AGO human QA pass for the
exact Docker-tested AI candidate. Output is a new private draft compatible
with existing Section34 governed review, NOT a GitHub write or approved PR.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from uuid import UUID

from ago.company_engineering import draft_github_commit_operation
from ago_engineering_candidate import inspect as inspect_run
from ago_human_qa_handoff import (
    LOCAL_OPENER,
    remote_json,
    verify_handoff,
)
from local_approved_agent_batch import founder_login, local_url

CONFIRM = "PREPARE_VERIFIED_QA_GITHUB_DRAFT"


def verified_qa(project_source: Path, stage: Path, qa_file: Path,
                *, base: str, token: str, opener=LOCAL_OPENER) -> dict:
    local = verify_handoff(project_source, stage, qa_file)
    me = remote_json(base, token, "/v1/console/me", opener=opener)
    if (not isinstance(me, dict) or "founder" not in me.get("roles", [])
            or "qa:read" not in me.get("permissions", [])):
        raise PermissionError("Authenticated Founder with QA read permission required")
    row = remote_json(
        base, token, "/v1/tasks/" + local["task_id"] + "/review", opener=opener,
    )
    if (not isinstance(row, dict) or str(row.get("task_id")) != local["task_id"]
            or row.get("verdict") != "pass"
            or not isinstance(row.get("author_id"), str)
            or not isinstance(row.get("reviewer_id"), str)
            or row["reviewer_id"] == row["author_id"]):
        raise PermissionError("Exact persisted independent human QA PASS required")
    prefix = (
        "AGO independent human QA; "
        "run=" + local["run_id"] + "; "
        "project=" + local["project_id"] + "; "
        "candidate_sha256=" + local["candidate_sha256"] + "; "
        "docker_receipt_sha256=" + local["test_receipt_sha256"] + "; "
        "tests=" + str(local["unittest_cases"]) + "; "
        "reviewer_notes="
    )
    detail = row.get("evidence")
    if not isinstance(detail, str) or not detail.startswith(prefix) or len(detail[len(prefix):].strip()) < 15:
        raise PermissionError("Human QA cannot be detached from the exact tested source")
    return {**local, "qa_reviewer_id": row["reviewer_id"],
            "independent_human_qa_verified": True}


def prepare_draft(
    export: Path, staged: Path, qa_packet: Path, destination: Path,
    *, base: str, token: str, github_project_id: str,
    operation_id: str, expected_sha: str, message: str,
    apply=False, confirm="", opener=LOCAL_OPENER,
) -> dict:
    evidence = verified_qa(
        export, staged, qa_packet, base=base, token=token, opener=opener,
    )
    UUID(github_project_id)
    UUID(operation_id)
    candidate = inspect_run(export)
    operation = draft_github_commit_operation(
        candidate, project_id=github_project_id, operation_id=operation_id,
        expected_sha=expected_sha, message=message,
    )
    result = {
        "kind": "ago_human_qa_verified_github_draft",
        "origin_run_id": evidence["run_id"],
        "origin_task_id": evidence["task_id"],
        "origin_project_id": evidence["project_id"],
        "github_project_id": github_project_id,
        "founder_reviewed_expected_sha": expected_sha,
        "candidate_sha256": evidence["candidate_sha256"],
        "docker_receipt_sha256": evidence["test_receipt_sha256"],
        "human_qa_reviewer_id": evidence["qa_reviewer_id"],
        "human_qa_verdict": "pass",
        "github_operation": operation,
        "remote_develop_head_verified": False,
        "independent_human_qa_verified": True,
        "github_write_authorized": False,
        "operation_submitted_to_ago": False,
        "github_committed": False,
        "release_ready": False,
    }
    if not apply:
        return {k: v for k, v in result.items() if k != "github_operation"}
    if confirm != CONFIRM:
        raise PermissionError("Explicit Founder GitHub draft confirmation required")
    repo = Path(__file__).resolve().parents[1]
    if (destination.resolve().is_relative_to(repo)
            or destination.is_symlink() or destination.exists()
            or not destination.parent.is_dir()):
        raise PermissionError("New private output outside Git checkout required")
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, sort_keys=True)
    return {k: v for k, v in result.items() if k != "github_operation"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--staged-directory", type=Path, required=True)
    parser.add_argument("--qa-packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--github-project-id", required=True)
    parser.add_argument("--operation-id", required=True)
    parser.add_argument("--expected-sha", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    a = parser.parse_args(argv)
    try:
        if a.apply and a.confirm != CONFIRM:
            raise PermissionError("Exact Founder confirmation required")
        base = local_url(a.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password, opener=LOCAL_OPENER)
        del password
        report = prepare_draft(
            a.export, a.staged_directory, a.qa_packet, a.output,
            base=base, token=token, github_project_id=a.github_project_id,
            operation_id=a.operation_id, expected_sha=a.expected_sha,
            message=a.message, apply=a.apply, confirm=a.confirm,
        )
        print(json.dumps(report, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "github_committed": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        print(json.dumps({
            "status": "blocked", "error_type": type(exc).__name__,
            "github_write_authorized": False, "github_committed": False,
            "release_ready": False,
        }), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
