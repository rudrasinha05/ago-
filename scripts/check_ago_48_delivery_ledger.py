"""Fail-closed inventory of the original 48 incomplete P0/P1/P2 gates.

This guard checks inventory completeness and bans self-certified completion.
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
    for item in tasks:
        if not isinstance(item, dict) or set(item) != {
            "id", "priority", "title", "status", "acceptance",
            "owner_local_or_external_evidence_required", "completion_proved",
        }:
            raise ValueError("Each gate must have the full exact contract")
        if type(item["id"]) is not int or item["priority"] not in IDS:
            raise ValueError("Numeric task ID and known priority required")
        if item["status"] not in ("partial", "pending") or item["completion_proved"] is not False:
            raise PermissionError("A checklist alone cannot certify a completed task")
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
    return {
        "schema": document["schema"],
        "total": 48,
        "per_priority": {key: len(expected) for key, expected in IDS.items()},
        "partial": sum(t["status"] == "partial" for t in tasks),
        "pending": sum(t["status"] == "pending" for t in tasks),
        "self_certified_completed": 0,
        "all_48_proven_complete": False,
    }


def main() -> None:
    doc = json.loads(FILE.read_text(encoding="utf-8"))
    print(json.dumps(validate(doc), sort_keys=True))


if __name__ == "__main__":
    main()
