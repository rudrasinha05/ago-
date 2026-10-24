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
    assert report["partial"] + report["pending"] == 48


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
