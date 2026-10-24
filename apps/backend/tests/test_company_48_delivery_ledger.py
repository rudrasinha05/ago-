"""A complete inventory is not a license to fake 48 completed deliveries."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/check_ago_48_delivery_ledger.py"
SPEC = importlib.util.spec_from_file_location("ago_48_ledger_guard", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def ledger():
    return json.loads(MODULE.FILE.read_text(encoding="utf-8"))


def test_all_48_p0_p1_p2_tasks_present_in_original_numbering():
    report = MODULE.validate(ledger())
    assert report["total"] == 48
    assert report["per_priority"] == {"P0": 12, "P1": 22, "P2": 14}
    assert report["self_certified_completed"] == 0
    assert report["all_48_proven_complete"] is False
    assert report["completed"] == 2
    assert report["completed_ids"] == [14, 45]
    assert report["completed"] + report["partial"] + report["pending"] == 48


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "reorder", "misgroup", "fake_completion", "fake_proof", "empty_acceptance"])
def test_any_missing_gate_or_false_completion_fails_closed(mutation):
    doc = ledger()
    if mutation == "missing":
        doc["tasks"].pop()
    elif mutation == "duplicate":
        doc["tasks"][-1] = copy.deepcopy(doc["tasks"][-2])
    elif mutation == "reorder":
        doc["tasks"][0], doc["tasks"][1] = doc["tasks"][1], doc["tasks"][0]
    elif mutation == "misgroup":
        doc["tasks"][0]["priority"] = "P2"
    elif mutation == "fake_completion":
        doc["tasks"][0]["status"] = "completed"
    elif mutation == "fake_proof":
        doc["tasks"][0]["completion_proved"] = True
    else:
        doc["tasks"][0]["acceptance"] = "done"
    with pytest.raises((ValueError, TypeError, PermissionError)):
        MODULE.validate(doc)


def test_original_ci_urls_and_owner_access_are_not_automatically_certified():
    doc = ledger()
    external = [t for t in doc["tasks"]
                if t["owner_local_or_external_evidence_required"]]
    assert len(external) >= 8
    assert all(t["completion_proved"] is False for t in external)
    doc["verified_p0_ci_baseline"]["architecture"] = "https://untrusted.example/green"
    with pytest.raises(ValueError, match="Official GitHub Actions"):
        MODULE.validate(doc)


@pytest.mark.parametrize("mutation", [
    "missing_proof", "wrong_sha", "wrong_run", "wrong_report",
    "wrong_test", "weak_limitation", "fake_external", "no_receipt",
])
def test_completion_requires_reviewed_ci_evidence(mutation):
    doc = ledger()
    if mutation == "missing_proof":
        del doc["completion_evidence"]["14"]
    elif mutation == "wrong_sha":
        doc["completion_evidence"]["14"]["sha"] = "f" * 40
    elif mutation == "wrong_run":
        doc["completion_evidence"]["45"]["backend"] = (
            "https://github.com/rudrasinha05/ago-/actions/runs/111"
        )
    elif mutation == "wrong_report":
        doc["completion_evidence"]["14"]["report"] = "docs/README.md"
    elif mutation == "wrong_test":
        doc["completion_evidence"]["45"]["tests"] = []
    elif mutation == "weak_limitation":
        doc["completion_evidence"]["14"]["limitation"] = "done"
    elif mutation == "fake_external":
        task = next(t for t in doc["tasks"] if t["id"] == 140)
        task["status"] = "completed"
        task["completion_proved"] = True
        doc["completion_evidence"]["140"] = copy.deepcopy(doc["completion_evidence"]["14"])
    else:
        task = next(t for t in doc["tasks"] if t["id"] == 120)
        task["status"] = "completed"
        task["completion_proved"] = True
    with pytest.raises((PermissionError, TypeError, ValueError)):
        MODULE.validate(doc)


def test_completed_gates_have_only_ci_scope_and_exact_pinned_sources():
    doc = ledger()
    assert sorted(int(key) for key in doc["completion_evidence"]) == [14, 45]
    for task in doc["tasks"]:
        if task["status"] == "completed":
            assert task["completion_proved"] is True
            assert task["owner_local_or_external_evidence_required"] is False
    assert MODULE.validate(doc)["self_certified_completed"] == 0
