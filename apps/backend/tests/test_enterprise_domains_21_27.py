"""Sections 21-27 domain policy negative and positive invariants.

These are the pure-policy gates. Durable database/API/browser acceptance remains
separately tracked in docs/SECTIONS21_27_SCOPE.md.
"""
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from ago.enterprise_domains import (
    ASSET_TYPES, HORIZONS, AssetIdentity, OperatingMode, WorkCandidate,
    WorkerState, allocate, allow_asset_use, budget_guard, evaluate_change,
    evidence_digest, operational_load, rollup_outcomes, transition_mode,
    transition_worker, twin_scenario, validate_horizon,
)


def _window(day: int) -> datetime:
    return datetime(2026, 10, day, tzinfo=timezone.utc)


@pytest.mark.parametrize("initial,target", [
    (OperatingMode.ACTIVE, OperatingMode.PAUSED),
    (OperatingMode.ACTIVE, OperatingMode.EMERGENCY),
    (OperatingMode.PAUSED, OperatingMode.MAINTENANCE),
    (OperatingMode.EMERGENCY, OperatingMode.PAUSED),
    (OperatingMode.SUSPENDED, OperatingMode.PAUSED),
])
def test_oos_approved_mode_changes(initial, target):
    assert transition_mode(initial, target, approved=True, reason="CEO reviewed") is target


@pytest.mark.parametrize("initial,target", [
    (OperatingMode.EMERGENCY, OperatingMode.ACTIVE),
    (OperatingMode.SUSPENDED, OperatingMode.ACTIVE),
    (OperatingMode.ACTIVE, OperatingMode.ACTIVE),
])
def test_oos_illegal_modes(initial, target):
    with pytest.raises(ValueError):
        transition_mode(initial, target, approved=True, reason="Review")


@pytest.mark.parametrize("approved,reason", [(False, "Review"), (True, "")])
def test_oos_mode_transition_refuses_unverified_approval(approved, reason):
    with pytest.raises(PermissionError):
        transition_mode(OperatingMode.ACTIVE, OperatingMode.PAUSED,
                        approved=approved, reason=reason)


def test_oos_worker_termination_cannot_be_reversed():
    assert transition_worker(WorkerState.UNAVAILABLE, WorkerState.TERMINATED,
                             approved=True, reason="Reviewed") == WorkerState.TERMINATED
    with pytest.raises(ValueError):
        transition_worker(WorkerState.TERMINATED, WorkerState.AVAILABLE,
                          approved=True, reason="Unsafe")
    with pytest.raises(PermissionError):
        transition_worker(WorkerState.AVAILABLE, WorkerState.PAUSED,
                          approved=False, reason="AI wants to pause")


def test_oos_workers_require_valid_state_change():
    with pytest.raises(ValueError):
        transition_worker(WorkerState.SLEEPING, WorkerState.AVAILABLE,
                          approved=True, reason="Skip transition")
    assert transition_worker(WorkerState.SLEEPING, WorkerState.IDLE,
                             approved=True, reason="Wake") == WorkerState.IDLE


def _candidate(name, *, priority=5, wait=1, eligible=True):
    return WorkCandidate(name, "task-" + name, priority, 4, 1, eligible,
                         eligible, WorkerState.AVAILABLE, wait)


def test_oos_allocation_deterministic_with_protected_eligibility():
    eligible = (_candidate("low", priority=1),
                _candidate("high", priority=9),
                _candidate("old", priority=9, wait=200),
                _candidate("blocked", priority=99, eligible=False))
    assert [c.employee for c in allocate(eligible, mode=OperatingMode.ACTIVE)] == [
        "old", "high", "low"]
    for mode in (OperatingMode.PAUSED, OperatingMode.EMERGENCY,
                 OperatingMode.MAINTENANCE, OperatingMode.SUSPENDED):
        assert allocate(eligible, mode=mode) == ()


def test_oos_capacity_exhausted_is_never_admitted():
    overloaded = WorkCandidate("a", "t", 10, 1, 2, True,
                               True, WorkerState.AVAILABLE, 0)
    sleeping = WorkCandidate("b", "t2", 10, 2, 1, True,
                             True, WorkerState.SLEEPING, 0)
    invalid_priority = WorkCandidate("c", "t3", 101, 2, 1, True,
                                     True, WorkerState.AVAILABLE, 0)
    assert allocate([overloaded, sleeping, invalid_priority],
                    mode=OperatingMode.ACTIVE) == ()


@pytest.mark.parametrize("running,queued,capacity,blocked", [
    (1, 2, 2, True), (1, 0, 2, False), (0, 0, 0, False), (1, 0, 0, True)
])
def test_agent_state_reports_operational_load_not_consciousness(running, queued, capacity, blocked):
    result = operational_load(running=running, queued=queued, capacity=capacity)
    assert result["overloaded"] is blocked
    assert result["subjective_consciousness"] is False


def test_agent_load_refuses_negative_inputs():
    for key in ("running", "queued", "capacity"):
        data = {"running": 0, "queued": 0, "capacity": 1}
        data[key] = -1
        with pytest.raises(ValueError):
            operational_load(**data)


def test_horizon_order_and_time_window():
    assert len(HORIZONS) == 9
    validate_horizon("lifetime", "five_year",
                     parent_start=_window(1), parent_end=_window(20),
                     child_start=_window(2), child_end=_window(10))


@pytest.mark.parametrize("parent,child,start,end", [
    ("monthly", "hourly", 2, 10),
    ("invalid", "annual", 2, 10),
    ("lifetime", "five_year", 1, 21),
    ("lifetime", "five_year", 9, 9),
])
def test_planning_rejects_invalid_horizons(parent, child, start, end):
    with pytest.raises(ValueError):
        validate_horizon(parent, child, parent_start=_window(1),
                         parent_end=_window(20), child_start=_window(start),
                         child_end=_window(end))


def test_planning_requires_timezones():
    with pytest.raises(ValueError):
        validate_horizon("lifetime", "five_year", parent_start=datetime(2026, 10, 1),
                         parent_end=_window(20), child_start=_window(2),
                         child_end=_window(10))


def test_governed_task_rollup_requires_real_qa():
    result = rollup_outcomes(tasks=[
        {"status": "completed", "qa": "pass"},
        {"status": "completed"},
        {"status": "failed", "qa": "not_reviewed"},
        {"status": "running"},
        {"status": "completed", "qa": "fail"},
    ])
    assert result == {"passed": 1, "failed": 2, "awaiting_evidence": 2}


def test_budget_parent_envelopes_and_remaining():
    assert budget_guard(company_limit="100", department_limit="80",
                        employee_limit="10", already_spent="2",
                        proposed_cost="3")["remaining"] == "5"


@pytest.mark.parametrize("limits,kind", [
    (("50", "60", "10", 0, 2), ValueError),
    (("100", "60", "80", 0, 2), ValueError),
    (("100", "50", "10", 9, 2), PermissionError),
    (("NaN", "50", "10", 9, 2), ValueError),
    (("-1", "0", "0", 0, 0), ValueError),
])
def test_budget_fail_closed(limits, kind):
    with pytest.raises(kind):
        budget_guard(company_limit=limits[0], department_limit=limits[1],
                     employee_limit=limits[2], already_spent=limits[3],
                     proposed_cost=limits[4])


def _asset():
    return AssetIdentity("tenantA", "publisher", "Data Library", "library",
                         "1.2.3", "MIT", "a" * 64)


def test_internal_marketplace_asset_identity_and_access():
    assert len(ASSET_TYPES) == 9
    asset = _asset()
    asset.validate()
    allow_asset_use(asset, requester_tenant="tenantA", published=True, authorized=True)


@pytest.mark.parametrize("tenant,published,authorized", [
    ("tenantB", True, True), ("tenantA", False, True),
    ("tenantA", True, False)
])
def test_marketplace_tenant_visibility_and_authorization(tenant, published, authorized):
    with pytest.raises(PermissionError):
        allow_asset_use(_asset(), requester_tenant=tenant,
                        published=published, authorized=authorized)


@pytest.mark.parametrize("changes", [
    {"kind": "executables"}, {"version": "v1"},
    {"sha256_digest": "bad"}, {"license": ""}, {"name": "x" * 201}
])
def test_marketplace_invalid_asset_fails(changes):
    from dataclasses import replace
    with pytest.raises(ValueError):
        replace(_asset(), **changes).validate()


def test_evolution_observed_delta_is_not_causation():
    before = [Decimal("10"), Decimal("20")]
    after = [Decimal("11"), Decimal("18")]
    evidence = [{"task_id": "1"}, {"task_id": "2"}]
    result = evaluate_change(baseline=before, candidate=after, evidence=evidence)
    assert result["mean_observed_delta"] == "-0.5"
    assert result["sample_count"] == 2
    assert result["evidence_digest"] == evidence_digest(evidence)
    assert result["causal_effect_proven"] is False and result["applied"] is False


@pytest.mark.parametrize("baseline,candidate,evidence", [
    ([], [], []),
    ([1], [1, 2], [{"task": "a"}]),
    ([1], [2], [{}]),
    ([1], [-2], [{"task": "a"}])
])
def test_evolution_missing_or_invalid_observations_denied(baseline, candidate, evidence):
    with pytest.raises(ValueError):
        evaluate_change(baseline=baseline, candidate=candidate, evidence=evidence)


def test_evolution_digest_has_bounds():
    with pytest.raises(ValueError):
        evidence_digest([])
    with pytest.raises(ValueError):
        evidence_digest([{}] * 1001)


def test_digital_twin_is_read_only_and_uncalibrated_without_evidence():
    twin = twin_scenario(workers=5, actions=10, cost_per_action="2",
                         budget="25", failure_pct=20, hiring=2, layoffs=1)
    assert twin["hypothetical_workers"] == 6
    assert twin["estimated_successful_actions"] == "8"
    assert twin["estimated_cost"] == "20"
    assert twin["within_budget"]
    assert twin["calibration"] == "uncalibrated"
    assert twin["read_only"] and not twin["applied"]


@pytest.mark.parametrize("changes", [
    {"workers": -1}, {"workers": 100001}, {"layoffs": 100},
    {"failure_pct": 120}, {"market_shock_pct": -101},
    {"cost_per_action": "-1"}, {"budget": "Infinity"}
])
def test_digital_twin_invalid_scenarios_denied(changes):
    values = {"workers": 5, "actions": 10, "cost_per_action": 1,
              "budget": 20, "failure_pct": 5}
    with pytest.raises(ValueError):
        twin_scenario(**{**values, **changes})


def test_digital_twin_unvalidated_data_is_not_certified_accuracy():
    x = twin_scenario(workers=1, actions=2, cost_per_action=1, budget=2,
                      failure_pct=0, observed_samples=100, market_shock_pct=20)
    assert x["calibration"] == "requires_validation"
    assert x["uncertainty"] == "unquantified"
    assert x["observed_revenue"] is None
