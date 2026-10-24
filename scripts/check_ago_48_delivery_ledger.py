"""Fail-closed inventory of the original 48 incomplete P0/P1/P2 gates.

This guard checks inventory completeness and only permits scoped, reviewed CI proof.
It does NOT turn source-code presence or a CI URL into proof of live user QA.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json"
IDS = {
    "P0": (10, 14, 15, 17, 18, 36, 45, 120, 133, 134, 156, 158),
    "P1": (19, 21, 22, 23, 26, 48, 58, 60, 61, 87, 119, 123,
           125, 126, 127, 128, 135, 138, 139, 140, 152, 154),
    "P2": (92, 94, 96, 97, 98, 129, 130, 147, 148, 149, 150, 155, 159, 160),
}


# Deliberately narrow gates: all other items still require separate human,
# device, external-system or project delivery acceptance.
CI_GATES = {
    14: ("docs/reports/SECTION14_FINAL_ACCEPTANCE.md",
         ("apps/backend/tests/test_section14_module_boundaries.py",)),
    45: ("docs/ARCHITECTURE_STATUS_AND_BACKLOG.md",
         ("tests/frontend/workspace.spec.mjs",
          "apps/backend/tests/test_company_dual_approval.py")),
}


def validate_ci_proof(item: dict, proof: dict, baseline: dict) -> None:
    task_id = item["id"]
    if task_id not in CI_GATES or item["owner_local_or_external_evidence_required"]:
        raise PermissionError("CI alone cannot close this task")
    report, tests = CI_GATES[task_id]
    if not isinstance(proof, dict) or set(proof) != {
        "sha", "architecture", "backend", "focused", "report", "tests",
        "scope", "limitation",
    }:
        raise PermissionError("Exact reviewed CI acceptance proof required")
    if any(proof[name] != baseline[name] for name in (
            "sha", "architecture", "backend", "focused")):
        raise PermissionError("Proof must identify the frozen reviewed CI baseline")
    if proof["report"] != report or proof["tests"] != list(tests):
        raise PermissionError("Cannot substitute evidence source paths")
    if not all((ROOT / name).is_file() for name in (report, *tests)):
        raise ValueError("An evidence source file is missing")
    if (not isinstance(proof["scope"], str) or len(proof["scope"]) < 55
            or not isinstance(proof["limitation"], str)
            or len(proof["limitation"]) < 50):
        raise ValueError("Acceptance must define scope and limitations")


def validate(document: dict) -> dict:
    if not isinstance(document, dict):
        raise TypeError("48-task delivery ledger must be an object")
    if document.get("schema") != "ago_p0_p1_p2_48_task_delivery_v1":
        raise ValueError("Unsupported delivery gate schema")
    tasks = document.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != 48:
        raise ValueError("Exactly 48 original incomplete tasks required")
    actual = {key: [] for key in IDS}
    titles = set()
    completed_ids = []
    for item in tasks:
        if not isinstance(item, dict) or set(item) != {
            "id", "priority", "title", "status", "acceptance",
            "owner_local_or_external_evidence_required", "completion_proved",
        }:
            raise ValueError("Each gate must have the full exact contract")
        if type(item["id"]) is not int or item["priority"] not in IDS:
            raise ValueError("Numeric task ID and known priority required")
        if item["status"] not in ("partial", "pending", "completed"):
            raise ValueError("Unknown delivery status")
        if type(item["completion_proved"]) is not bool or (item["status"] == "completed") != item["completion_proved"]:
            raise PermissionError("Status and completion proof must agree")
        if item["status"] == "completed":
            completed_ids.append(item["id"])
        if type(item["owner_local_or_external_evidence_required"]) is not bool:
            raise TypeError("Explicit owner/third-party evidence flag required")
        if (not isinstance(item["title"], str) or len(item["title"].strip()) < 8
                or not isinstance(item["acceptance"], str)
                or len(item["acceptance"].strip()) < 35):
            raise ValueError("Concrete task title and acceptance condition required")
        if item["title"] in titles:
            raise ValueError("Duplicate task title")
        titles.add(item["title"])
        actual[item["priority"]].append(item["id"])
    for phase, expected in IDS.items():
        if tuple(actual[phase]) != expected:
            raise ValueError("Missing, duplicate or out-of-order " + phase + " task")
    baseline = document.get("verified_p0_ci_baseline", {})
    if not isinstance(baseline, dict) or not re.fullmatch(
        r"[a-f0-9]{40}", baseline.get("sha", "")
    ):
        raise ValueError("Source-backed original CI SHA required")
    for name in ("backend", "architecture", "focused"):
        url = baseline.get(name)
        if not isinstance(url, str) or not re.fullmatch(
            r"https://github\.com/rudrasinha05/ago-/actions/runs/[0-9]+", url
        ):
            raise ValueError("Official GitHub Actions source for " + name + " required")
    proofs = document.get("completion_evidence", {})
    if not isinstance(proofs, dict) or set(proofs) != {str(i) for i in completed_ids}:
        raise PermissionError("Each completed gate needs one matching proof")
    for item in tasks:
        if item["status"] == "completed":
            validate_ci_proof(item, proofs[str(item["id"])], baseline)
    return {
        "schema": document["schema"],
        "total": 48,
        "per_priority": {key: len(expected) for key, expected in IDS.items()},
        "partial": sum(t["status"] == "partial" for t in tasks),
        "pending": sum(t["status"] == "pending" for t in tasks),
        "completed": len(completed_ids),
        "completed_ids": completed_ids,
        "self_certified_completed": 0,
        "all_48_proven_complete": len(completed_ids) == 48,
    }


def main() -> None:
    doc = json.loads(FILE.read_text(encoding="utf-8"))
    print(json.dumps(validate(doc), sort_keys=True))


if __name__ == "__main__":
    main()
