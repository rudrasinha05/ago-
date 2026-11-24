"""Version a Founder's edits separately from the governed employee run."""
from __future__ import annotations

import json

from ago.company_engineering import reviewed_candidate, verify_persisted_candidate


class RevisionConflict(ValueError):
    pass


def workspace_snapshot(row, draft):
    if not row:
        raise LookupError("Project stage task not found")
    result = row["run_result"] or {}
    if row["run_status"] != "completed" or not result.get("engineering_candidate"):
        raise LookupError("This task has no completed engineering candidate")
    original = verify_persisted_candidate(result["engineering_candidate"])
    current = verify_persisted_candidate(draft["candidate"]) if draft else original
    return {
        "run_id": str(row["run_id"]),
        "revision": draft["revision"] if draft else 0,
        "original_sha256": original["candidate_sha256"],
        "candidate_sha256": current["candidate_sha256"],
        "files": current["files"],
        "acceptance_checks": current["acceptance_checks"],
    }


def edited_candidate(snapshot, changes):
    if not isinstance(changes, dict) or set(changes) != {"run_id", "expected_revision", "files"}:
        raise ValueError("run_id, expected_revision and files are required")
    revision = changes["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid workspace revision")
    if changes["run_id"] != snapshot["run_id"] or revision != snapshot["revision"]:
        raise RevisionConflict("Workspace changed. Reload before saving.")
    return reviewed_candidate(json.dumps({
        "files": changes["files"], "acceptance_checks": snapshot["acceptance_checks"],
    }))
