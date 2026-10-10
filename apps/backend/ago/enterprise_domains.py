"""AGO Sections 21–27 — pure, conservative organizational domain policy.

No I/O, database, privilege mutation, payment, model inference or provider calls.
State decisions here are **guards**; persistence and authorization must be
provided by the existing audited application/service ports.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from hashlib import sha256
from json import dumps
from typing import Mapping, Sequence


class OperatingMode(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    MAINTENANCE = "maintenance"
    EMERGENCY = "emergency"
    SUSPENDED = "suspended"


class WorkerState(str, Enum):
    AVAILABLE = "available"
    IDLE = "idle"
    PAUSED = "paused"
    SLEEPING = "sleeping"
    INTERRUPTED = "interrupted"
    UNAVAILABLE = "unavailable"
    TERMINATED = "terminated"


_MODE_TRANSITIONS = {
    OperatingMode.ACTIVE: {OperatingMode.PAUSED, OperatingMode.MAINTENANCE,
                           OperatingMode.EMERGENCY, OperatingMode.SUSPENDED},
    OperatingMode.PAUSED: {OperatingMode.ACTIVE, OperatingMode.MAINTENANCE,
                           OperatingMode.EMERGENCY, OperatingMode.SUSPENDED},
    OperatingMode.MAINTENANCE: {OperatingMode.ACTIVE, OperatingMode.PAUSED,
                                OperatingMode.EMERGENCY},
    OperatingMode.EMERGENCY: {OperatingMode.PAUSED, OperatingMode.MAINTENANCE},
    OperatingMode.SUSPENDED: {OperatingMode.PAUSED},
}
_WORKER_TRANSITIONS = {
    WorkerState.AVAILABLE: {WorkerState.IDLE, WorkerState.PAUSED,
                            WorkerState.INTERRUPTED, WorkerState.UNAVAILABLE},
    WorkerState.IDLE: {WorkerState.AVAILABLE, WorkerState.PAUSED,
                       WorkerState.SLEEPING, WorkerState.UNAVAILABLE},
    WorkerState.PAUSED: {WorkerState.AVAILABLE, WorkerState.IDLE,
                         WorkerState.SLEEPING, WorkerState.UNAVAILABLE},
    WorkerState.SLEEPING: {WorkerState.IDLE, WorkerState.UNAVAILABLE},
    WorkerState.INTERRUPTED: {WorkerState.PAUSED, WorkerState.UNAVAILABLE},
    WorkerState.UNAVAILABLE: {WorkerState.IDLE, WorkerState.TERMINATED},
    WorkerState.TERMINATED: set(),
}


def transition_mode(current: OperatingMode, target: OperatingMode,
                    *, approved: bool, reason: str) -> OperatingMode:
    """Constitutional approval must be verified by the caller, not by AI text."""
    if not approved or not reason.strip():
        raise PermissionError("Exact authorized mode change and reason required")
    if target not in _MODE_TRANSITIONS[current]:
        raise ValueError("Illegal organizational transition")
    return target


def transition_worker(current: WorkerState, target: WorkerState,
                      *, approved: bool, reason: str) -> WorkerState:
    if not approved or not reason.strip():
        raise PermissionError("Authorized, audited worker change required")
    if target not in _WORKER_TRANSITIONS[current]:
        raise ValueError("Illegal employee transition")
    return target


@dataclass(frozen=True)
class WorkCandidate:
    employee: str
    task_id: str
    priority: int
    available_units: int
    required_units: int
    dependency_qa_passed: bool
    task_approved: bool
    worker_state: WorkerState
    oldest_wait_seconds: int


def allocate(candidates: Sequence[WorkCandidate], *,
             mode: OperatingMode) -> tuple[WorkCandidate, ...]:
    """Stable, capacity-bounded advisory admission; no execution is authorized."""
    if mode is not OperatingMode.ACTIVE:
        return ()
    eligible = sorted((
        c for c in candidates
        if c.task_approved and c.dependency_qa_passed
        and c.worker_state in (WorkerState.AVAILABLE, WorkerState.IDLE)
        and 0 < c.required_units <= c.available_units
        and 0 <= c.priority <= 100 and c.oldest_wait_seconds >= 0
    ), key=lambda x: (-x.priority, -x.oldest_wait_seconds, x.task_id, x.employee))
    remaining: dict[str, int] = {}
    chosen: list[WorkCandidate] = []
    for candidate in eligible:
        units = remaining.setdefault(candidate.employee, candidate.available_units)
        if candidate.required_units <= units:
            remaining[candidate.employee] -= candidate.required_units
            chosen.append(candidate)
    return tuple(chosen)


def operational_load(*, running: int, queued: int, capacity: int) -> dict:
    """A load indicator, **not** an assertion about consciousness or emotions."""
    if min(running, queued) < 0 or capacity < 0:
        raise ValueError("Counts and capacity must be nonnegative")
    load = running + queued
    return {
        "load": load, "capacity": capacity,
        "overloaded": load > capacity or (capacity == 0 and load > 0),
        "availability": "unknown" if capacity == 0 else
                        ("overloaded" if load > capacity else "available"),
        "subjective_consciousness": False,
    }


HORIZONS = ("lifetime", "five_year", "annual", "quarterly",
            "monthly", "weekly", "daily", "hourly", "current_task")


def validate_horizon(parent: str, child: str, *,
                     parent_start: datetime, parent_end: datetime,
                     child_start: datetime, child_end: datetime) -> None:
    """Each child must be the next planning level, within parent limits."""
    if parent not in HORIZONS or child not in HORIZONS:
        raise ValueError("Unknown planning horizon")
    if HORIZONS.index(child) != HORIZONS.index(parent) + 1:
        raise ValueError("Invalid planning hierarchy")
    if any(x.tzinfo is None for x in
           (parent_start, parent_end, child_start, child_end)):
        raise ValueError("Timezone-aware planning windows required")
    if not parent_start < parent_end or not (
        parent_start <= child_start < child_end <= parent_end
    ):
        raise ValueError("Child outside parent planning window")


def rollup_outcomes(*, tasks: Sequence[Mapping[str, str]]) -> dict:
    """No invented denominator: a task only counts if QA is evidenced."""
    counts = {"passed": 0, "failed": 0, "awaiting_evidence": 0}
    for task in tasks:
        if task.get("status") == "completed" and task.get("qa") == "pass":
            counts["passed"] += 1
        elif task.get("status") == "failed" or task.get("qa") == "fail":
            counts["failed"] += 1
        else:
            counts["awaiting_evidence"] += 1
    return counts


def _amount(value: Decimal | str | int) -> Decimal:
    try:
        amount = Decimal(str(value))
    except InvalidOperation as exc:
        raise ValueError("Invalid decimal amount") from exc
    if not amount.is_finite() or amount < 0:
        raise ValueError("Amounts must be finite and nonnegative")
    return amount


def budget_guard(*, company_limit: Decimal | str | int,
                 department_limit: Decimal | str | int,
                 employee_limit: Decimal | str | int,
                 already_spent: Decimal | str | int,
                 proposed_cost: Decimal | str | int) -> dict:
    """Budget envelopes cannot exceed their parents or existing cap."""
    root, dept, employee, spent, proposed = map(
        _amount, (company_limit, department_limit, employee_limit,
                  already_spent, proposed_cost))
    if not (employee <= dept <= root):
        raise ValueError("Child budgets exceed parent limit")
    if spent + proposed > employee:
        raise PermissionError("Insufficient approved spending envelope")
    return {"remaining": str(employee - spent - proposed),
            "kind": "budget_guard", "money_observed": False}


ASSET_TYPES = frozenset((
    "service", "library", "dataset", "research", "design_system",
    "template", "agent", "model", "workflow"
))


@dataclass(frozen=True)
class AssetIdentity:
    tenant_id: str
    publisher_id: str
    name: str
    kind: str
    version: str
    license: str
    sha256_digest: str

    def validate(self) -> None:
        if self.kind not in ASSET_TYPES:
            raise ValueError("Unsupported marketplace asset type")
        for item in (self.tenant_id, self.publisher_id, self.name,
                     self.license, self.version):
            if not item.strip() or len(item) > 200:
                raise ValueError("Invalid asset identity")
        if len(self.sha256_digest) != 64 or any(
            c not in "0123456789abcdef" for c in self.sha256_digest
        ):
            raise ValueError("Unverifiable content digest")
        major_minor_patch = self.version.split(".")
        if len(major_minor_patch) != 3 or not all(x.isdigit() for x in major_minor_patch):
            raise ValueError("Version must be major.minor.patch")


def allow_asset_use(asset: AssetIdentity, *, requester_tenant: str,
                    published: bool, authorized: bool) -> None:
    asset.validate()
    if asset.tenant_id != requester_tenant or not published or not authorized:
        raise PermissionError("Asset use requires published tenant-owned access")


def evidence_digest(entries: Sequence[Mapping[str, object]]) -> str:
    if not 1 <= len(entries) <= 1000:
        raise ValueError("Bounded evidence sample required")
    return sha256(dumps(entries, sort_keys=True, separators=(",", ":"),
                        allow_nan=False, default=str).encode()).hexdigest()


def evaluate_change(*, baseline: Sequence[Decimal | int | str],
                    candidate: Sequence[Decimal | int | str],
                    evidence: Sequence[Mapping[str, object]]) -> dict:
    """Observed deltas, not causal claims or automatic policy promotion."""
    if not baseline or len(baseline) != len(candidate):
        raise ValueError("Matched nonempty observation pairs required")
    if len(baseline) != len(evidence):
        raise ValueError("Every observation needs provenance evidence")
    if any(not item for item in evidence):
        raise ValueError("Empty evidence not permitted")
    before, after = [_amount(x) for x in baseline], [_amount(x) for x in candidate]
    result = sum((y - x for x, y in zip(before, after)), Decimal(0)) / len(before)
    return {"mean_observed_delta": str(result), "sample_count": len(before),
            "evidence_digest": evidence_digest(evidence),
            "causal_effect_proven": False, "applied": False}


def twin_scenario(*, workers: int, failure_pct: int,
                  actions: int, cost_per_action: Decimal | str | int,
                  budget: Decimal | str | int, observed_samples: int = 0,
                  hiring: int = 0, layoffs: int = 0,
                  market_shock_pct: int = 0) -> dict:
    """Deterministic read-only counterfactual with explicit uncertainty."""
    if any(not 0 <= v <= 100000 for v in
           (workers, actions, observed_samples, hiring, layoffs)):
        raise ValueError("Scenario exceeds bounded limits")
    if layoffs > workers + hiring:
        raise ValueError("Cannot dismiss more hypothetical workers than present")
    if not 0 <= failure_pct <= 100 or not -100 <= market_shock_pct <= 100:
        raise ValueError("Invalid scenario percentage")
    unit = _amount(cost_per_action)
    cap = _amount(budget)
    anticipated = unit * actions
    surviving = Decimal(actions) * (100 - failure_pct) / 100
    shock = Decimal(100 + market_shock_pct) / 100
    return {
        "hypothetical_workers": workers + hiring - layoffs,
        "estimated_successful_actions": str(surviving * shock),
        "estimated_cost": str(anticipated),
        "within_budget": anticipated <= cap,
        "calibration": "uncalibrated" if observed_samples < 30 else "requires_validation",
        "uncertainty": "high" if observed_samples < 30 else "unquantified",
        "assumptions": {"failure_pct": failure_pct, "market_shock_pct": market_shock_pct},
        "read_only": True, "applied": False, "observed_revenue": None,
    }
