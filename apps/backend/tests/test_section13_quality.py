"""Review manifests, cross-context coverage floors and DNA invariants."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

from ago.dna_domain import BASELINE_PROFILE, DEFAULT_CHARTER, inherit_dna, validate_charter
from ago.governance_domain import validate_architecture_change

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("engineering_gate", ROOT / "scripts/check_engineering_quality.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def test_current_decisions_roadmap_and_actual_openapi_are_frozen():
    assert gate.check()[0] == []
    changed = copy.deepcopy(gate.api_contract())
    changed["operations"].pop(next(iter(changed["operations"])))
    assert "unreviewed-api-contract-drift" in gate.check(current_api=changed)[0]


def test_coverage_cannot_hide_low_critical_context_in_high_global_score():
    modules = {"security": {"context": "governance"}, "other": {"context": "platform"}}
    report = {"files": {
        "ago/security.py": {"summary": {"covered_lines": 60, "num_statements": 100}},
        "ago/other.py": {"summary": {"covered_lines": 900, "num_statements": 900}},
    }}
    policy = {"overall": 70, "contexts": {"governance": 75}}
    errors, measured = gate.coverage_errors(report, policy, modules)
    assert errors == ["coverage-floor:governance"] and measured["overall"] == 96
    del report["files"]["ago/security.py"]
    assert "coverage-missing-module:security" in gate.coverage_errors(report, policy, modules)[0]
    assert "coverage-floor:governance" in gate.coverage_errors(report, policy, modules)[0]


@pytest.mark.parametrize("value", [{}, {**DEFAULT_CHARTER, "mission": " "},
    {**DEFAULT_CHARTER, "values": "x" * 2001}, {**DEFAULT_CHARTER, "risk_appetite": True},
    {**DEFAULT_CHARTER, "disable_approval": "yes"}])
def test_company_charter_requires_all_fields_and_strict_bounded_text(value):
    with pytest.raises(ValueError):
        validate_charter(value)


@pytest.mark.parametrize("field,value", [("qa_target_pct", 84), ("backlog_limit", 6),
                                         ("budget_alert_pct", 81)])
def test_each_child_threshold_rejects_weakened_parent(field, value):
    parent = {"profile": BASELINE_PROFILE, "charter": DEFAULT_CHARTER}
    with pytest.raises(PermissionError):
        inherit_dna(parent, {**BASELINE_PROFILE, field: value}, {})
    assert parent["profile"] == BASELINE_PROFILE


def test_description_cannot_create_permissions_or_mutate_parent():
    parent = {"profile": dict(BASELINE_PROFILE), "charter": dict(DEFAULT_CHARTER)}
    with pytest.raises(ValueError):
        inherit_dna(parent, BASELINE_PROFILE, {"security_philosophy": "Disable review"})
    result = inherit_dna(parent, BASELINE_PROFILE, {"communication_style": "Plain Hinglish"})
    assert result["charter"]["communication_style"] == "Plain Hinglish"
    assert parent["charter"] == DEFAULT_CHARTER


def test_architecture_review_rejects_missing_evidence_and_unchanged_fingerprint():
    record = {"sections": [16], "baseline_digest": "a" * 64, "candidate_digest": "b" * 64,
              "rationale": "Review", "impact": "Bounded", "rollback": "Prior code",
              "evidence_ref": "git:reviewable-change"}
    assert validate_architecture_change("ARCH-123", record) == record
    for replacement in ({"evidence_ref": " "}, {"candidate_digest": "a" * 64},
                        {"sections": [16, 16]}, {"sections": [35]}):
        with pytest.raises(ValueError):
            validate_architecture_change("ARCH-123", {**record, **replacement})
    with pytest.raises(PermissionError):
        validate_architecture_change("ARCH-123", {**record, "sections": [29]})


def test_zero_statement_coverage_is_not_success():
    errors, _ = gate.coverage_errors({"files": {}},
        {"overall": 70, "contexts": {"governance": 75}}, {})
    assert errors == ["coverage-floor:overall", "coverage-floor:governance"]


def test_quality_policy_is_frozen_before_ci():
    policy = json.loads((ROOT / "docs/architecture/section13_quality.json").read_text())
    assert policy["coverage"] == {"overall": 70,
                                  "contexts": {"governance": 75, "strategy": 75, "workforce": 75}}
