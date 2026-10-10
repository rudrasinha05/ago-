"""M7 frozen DNA thresholds, deterministic risk scoring and RBAC safety."""
from uuid import uuid4

import pytest

from ago.executive_intelligence import evaluate
from ago.m7_permissions import ROLE_PERMISSIONS, grant_existing_role
from ago.organizational_dna import BASELINE_PROFILE, validate_profile


def evidence(*, total=0, completed=0, qa=0, backlog=0,
             configured=False, ceiling="0", consumed="0"):
    return {
        "total_tasks": total, "completed_tasks": completed, "qa_pass": qa,
        "backlog_tasks": backlog, "budget_configured": configured,
        "budget_ceiling": ceiling, "budget_consumed": consumed,
    }


def test_insufficient_operational_data_has_no_fabricated_fitness():
    result = evaluate(evidence(), BASELINE_PROFILE)
    assert result["fitness"] is None
    assert result["risk_flags"] == ["insufficient_data"]
    assert result["simulation_only"] is True


def test_frozen_weighted_score_and_risk_flags():
    metrics = evidence(
        total=3, completed=1, qa=0, backlog=2,
        configured=True, ceiling="10", consumed="9",
    )
    profile = {**BASELINE_PROFILE, "backlog_limit": 0}
    result = evaluate(metrics, profile)
    assert set(result["risk_flags"]) == {
        "qa_below_target", "backlog_over_limit", "budget_alert",
    }
    assert result["quality_pct"] == "0.00"
    assert result["credit_utilization_pct"] == "90.00"
    assert result["fitness"] == "13.67"
    with_no_backlog_warning = evaluate(
        metrics, {**profile, "backlog_limit": 5, "budget_alert_pct": 95},
    )
    assert with_no_backlog_warning["risk_flags"] == ["qa_below_target"]
    assert with_no_backlog_warning["fitness"] == result["fitness"]


@pytest.mark.parametrize(
    "profile",
    [
        {},
        {"qa_target_pct": True, "backlog_limit": 5, "budget_alert_pct": 80},
        {"qa_target_pct": 50, "backlog_limit": -1, "budget_alert_pct": 80},
        {"qa_target_pct": 40, "backlog_limit": 3, "budget_alert_pct": 90},
        {**BASELINE_PROFILE, "disable_human_approval": True},
    ],
)
def test_dna_cannot_change_constitution_or_use_unbounded_thresholds(profile):
    with pytest.raises(ValueError):
        validate_profile(profile)


@pytest.mark.parametrize(
    "metric",
    [
        evidence(total=1, completed=2),
        evidence(total=1, completed=1, qa=2),
        evidence(total=1, backlog=-1),
        evidence(total=1, completed=1, configured=True, ceiling="1", consumed="2"),
    ],
)
def test_invalid_metric_evidence_is_rejected(metric):
    with pytest.raises(ValueError):
        evaluate(metric, BASELINE_PROFILE)


def test_role_upgrades_never_happen_silently():
    with pytest.raises(PermissionError):
        grant_existing_role(
            None, tenant_id=str(uuid4()), role="founder",
        )
    with pytest.raises(ValueError):
        grant_existing_role(
            None, tenant_id=str(uuid4()), role="admin", confirmed=True,
        )
    assert "meta:dna:activate" not in ROLE_PERMISSIONS["reviewer"]
    assert "meta:observe" not in ROLE_PERMISSIONS["reviewer"]
    assert "meta:read" in ROLE_PERMISSIONS["reviewer"]
