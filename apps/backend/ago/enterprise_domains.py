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


LIFECYCLE_PHASES = ("sense", "classify", "prioritize", "allocate", "coordinate",
                    "monitor", "escalate", "learn")


def next_lifecycle_phase(previous: str | None) -> str:
    if previous is None:
        return LIFECYCLE_PHASES[0]
    if previous not in LIFECYCLE_PHASES:
        raise ValueError("Unknown lifecycle checkpoint; recovery review required")
    return LIFECYCLE_PHASES[(LIFECYCLE_PHASES.index(previous)+1) % len(LIFECYCLE_PHASES)]


def controlled_assignment(task_ids: Sequence[str], seed: str) -> dict:
    """Reproducible balanced assignment before outcomes; seed is immutable."""
    from uuid import UUID
    ids = [str(UUID(x)) for x in task_ids]
    if not 2 <= len(ids) <= 100 or len(set(ids)) != len(ids) or not 1 <= len(seed.strip()) <= 160:
        raise ValueError("Unique bounded prospective cohort and seed required")
    ordered = sorted(ids, key=lambda x: sha256((seed+":"+x).encode()).hexdigest())
    return {x: "baseline" if i % 2 == 0 else "candidate" for i, x in enumerate(ordered)}


def forecast_runtime(training: Sequence[dict], cohort: Sequence[dict]) -> dict:
    """Empirical baseline and interval, strictly frozen before cohort outcomes."""
    values = sorted(float(t["elapsed_seconds"]) for t in training
                    if t.get("elapsed_seconds") is not None and t["elapsed_seconds"] >= 0)
    center = sum(values)/len(values) if values else None
    interval = [values[0], values[-1]] if values else None
    return {"model_version": "empirical_elapsed_baseline_v1", "training_samples": len(values),
            "mean_elapsed_seconds": center, "empirical_range_seconds": interval,
            "tasks": [{"task_id": str(t["id"]), "deadline": t.get("deadline"),
                       "created_at": t["created_at"]} for t in cohort],
            "limitations": "Elapsed time includes approval waits; range is empirical, not a confidence guarantee."}


def calibrate_runtime(prediction: dict, outcomes: Sequence[dict]) -> dict:
    index = {str(t["id"]): t for t in outcomes}
    ids = {t["task_id"] for t in prediction["tasks"]}
    if len(index) != len(outcomes) or not index.keys() <= ids:
        raise ValueError("Unique same-cohort runtime outcomes required")
    mean, interval = prediction["mean_elapsed_seconds"], prediction["empirical_range_seconds"]
    observed, deadline_observed, deadline_errors = [], 0, []
    from datetime import datetime
    for t in prediction["tasks"]:
        row = index.get(t["task_id"])
        if not row or row.get("elapsed_seconds") is None:
            continue
        value = float(row["elapsed_seconds"])
        if value < 0:
            raise ValueError("Invalid observed elapsed time")
        observed.append(value)
        if t.get("deadline") and mean is not None:
            deadline = datetime.fromisoformat(t["deadline"])
            created = datetime.fromisoformat(t["created_at"])
            deadline_observed += 1
            allowance = (deadline-created).total_seconds()
            deadline_errors.append(int((mean <= allowance) != (value <= allowance)))
    return {"observed_samples": len(observed), "pending_samples": len(ids)-len(observed),
            "mean_absolute_error_seconds": sum(abs(mean-x) for x in observed)/len(observed)
              if mean is not None and observed else None,
            "empirical_range_coverage": sum(interval[0] <= x <= interval[1] for x in observed)/len(observed)
              if interval and observed else None,
            "deadline_observed_samples": deadline_observed,
            "deadline_classification_error_rate": sum(deadline_errors)/deadline_observed
              if deadline_observed else None, "accuracy_certified": False,
            "unknown_dimensions": ["revenue", "growth", "market", "hiring_causality"]}


def finance_analysis(rows: Sequence[dict], *, currency: str,
                     baseline_revenue: str, alternative_net: str,
                     assumptions: str) -> dict:
    """Observed scenario accounting; never authenticates invoices or money."""
    if len(currency) != 3 or not currency.isascii() or not currency.isalpha() or not currency.isupper():
        raise ValueError("Three-letter currency required")
    if not 1 <= len(assumptions.strip()) <= 2000:
        raise ValueError("Explicit economic assumptions required")
    if not rows or len(rows) > 1000 or any(r["currency"] != currency for r in rows):
        raise ValueError("Nonempty single-currency evidence required")
    baseline, alternative = _amount(baseline_revenue), _amount(alternative_net)
    revenue = sum((_amount(str(r["observed_amount"])) for r in rows
                   if r["category"] == "revenue"), Decimal(0))
    costs = sum((_amount(str(r["observed_amount"])) for r in rows
                 if r["category"] != "revenue"), Decimal(0))
    net = revenue - costs
    return {"currency": currency, "observed_cost": str(costs),
            "observed_revenue": str(revenue), "observed_net": str(net),
            "baseline_revenue": str(baseline), "alternative_net": str(alternative),
            "incremental_roi_pct": str((revenue-baseline-costs)*100/costs) if costs else None,
            "opportunity_cost": str(max(Decimal(0), alternative-net)),
            "assumptions": assumptions.strip(), "financial_settlement": False,
            "evidence_state": "operator_claims_not_provider_authenticated",
            "optimization": "advisory; preserve safety, approvals and QA"}


def forecast_quality(training: Sequence[dict], cohort: Sequence[dict]) -> dict:
    """QA-only baseline; frozen cohort is excluded from training by caller."""
    if len(training) > 1000 or len(cohort) > 1000:
        raise ValueError("Bounded task cohorts required")
    outcomes = [r["verdict"] == "pass" and r["status"] == "completed"
                for r in training if r.get("verdict") in ("pass", "fail")]
    rate = sum(outcomes) / len(outcomes) if outcomes else None
    from math import sqrt
    interval = None
    if outcomes:
        n, z = len(outcomes), 1.96
        center = (rate+z*z/(2*n))/(1+z*z/n)
        half = z*sqrt(rate*(1-rate)/n+z*z/(4*n*n))/(1+z*z/n)
        interval = [round(max(0, center-half), 6), round(min(1, center+half), 6)]
    return {"model_version": "qa_cohort_baseline_v1", "training_samples": len(outcomes),
            "pass_probability": rate, "probability_interval_95": interval,
            "cohort_task_ids": [str(r["id"]) for r in cohort],
            "expected_qa_passes": rate*len(cohort) if rate is not None else None,
            "calibrated": False, "applied": False,
            "limitations": "QA outcome baseline; no cycle-time, revenue or hiring causality."}


def calibrate_quality(prediction: dict, observations: Sequence[dict]) -> dict:
    ids = set(prediction["cohort_task_ids"])
    if len(ids) != len(prediction["cohort_task_ids"]):
        raise ValueError("Unique frozen cohort required")
    if any(str(r["id"]) not in ids for r in observations):
        raise ValueError("Outcome outside forecast cohort")
    if len({str(r["id"]) for r in observations}) != len(observations):
        raise ValueError("Duplicate outcomes denied")
    eligible = [r for r in observations if r.get("verdict") in ("pass", "fail")]
    rate = prediction["pass_probability"]
    if rate is not None and (type(rate) not in (float, int) or not 0 <= rate <= 1):
        raise ValueError("Invalid forecast probability")
    outcomes = [int(r["verdict"] == "pass" and r["status"] == "completed")
                for r in eligible]
    complete = bool(ids) and len(eligible) == len(ids)
    brier = sum((rate-y)**2 for y in outcomes)/len(outcomes) if (
        rate is not None and outcomes) else None
    return {"cohort_size": len(ids), "observed_samples": len(outcomes),
            "pending_samples": len(ids)-len(outcomes), "complete": complete,
            "brier_score": brier,
            "mean_absolute_error": sum(abs(rate-y) for y in outcomes)/len(outcomes)
             if rate is not None and outcomes else None,
            "observed_qa_passes": sum(outcomes),
            "calibration_status": "held_out_measured" if complete and brier is not None
             else "awaiting_observations_or_training", "accuracy_certified": False,
            "applied": False, "limits": "Single frozen QA cohort; no general accuracy guarantee."}


EXPENSE_CATEGORIES = ("model", "storage", "execution", "tool", "time")
QUALITY_DIMENSIONS = ("prompt", "architecture", "workflow", "department", "employee")


def metric_number(value: object) -> Decimal:
    """Signed, bounded measurements; unknown is never coerced to zero."""
    if isinstance(value, bool):
        raise ValueError("Finite bounded measurement required")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("Finite bounded measurement required") from exc
    if not number.is_finite() or abs(number) > Decimal("1e18"):
        raise ValueError("Finite bounded measurement required")
    return number


def measured_economics(rows: Sequence[dict], qa: Sequence[dict], *, currency: str) -> dict:
    analysis = finance_analysis(rows, currency=currency, baseline_revenue="0",
                                alternative_net="0", assumptions="Reviewed exact-period accounting")
    totals = {}
    for row in rows:
        category = row["category"]
        totals[category] = totals.get(category, Decimal(0)) + _amount(str(row["observed_amount"]))
    passed = sum(r["verdict"] == "pass" and r["status"] == "completed" for r in qa)
    cost_known = any(k != "revenue" for k in totals)
    revenue_known = "revenue" in totals
    return {"currency": currency, "observed_cost": analysis["observed_cost"] if cost_known else None,
            "observed_revenue": analysis["observed_revenue"] if revenue_known else None,
            "observed_net": analysis["observed_net"] if cost_known and revenue_known else None,
            "category_totals": {k: str(v) for k, v in totals.items()},
            "missing_expense_categories": [k for k in EXPENSE_CATEGORIES if k not in totals],
            "qa_samples": len(qa), "qa_passed": passed,
            "qa_pass_rate": passed/len(qa) if qa else None,
            "cost_per_qa_output": str(Decimal(analysis["observed_cost"])/passed) if passed and cost_known else None,
            "provider_authenticated": False, "financial_settlement": False,
            "limits": "Reviewed supplied records; absent categories and unreported value remain unknown. QA denominator is the selected cohort."}


def compare_measured_economics(baseline: dict, candidate: dict, alternative: dict | None = None) -> dict:
    if any(r.get(k) is None for r in [baseline, candidate] + ([alternative] if alternative else [])
           for k in ("observed_cost", "observed_net")):
        raise ValueError("Explicit measured costs and revenue required; missing records are unknown")
    if baseline["currency"] != candidate["currency"] or (
        alternative and alternative["currency"] != candidate["currency"]
    ):
        raise ValueError("Same-currency measured periods required")
    def daily(row, field):
        duration = metric_number(row["duration_days"])
        if duration <= 0:
            raise ValueError("Positive measured duration required")
        return metric_number(row[field])/duration
    before, after = daily(baseline, "observed_net"), daily(candidate, "observed_net")
    cost_before, cost_after = daily(baseline, "observed_cost"), daily(candidate, "observed_cost")
    quality = baseline["qa_pass_rate"] is not None and candidate["qa_pass_rate"] is not None
    safeguards = {"quality_nonregression": candidate["qa_pass_rate"] >= baseline["qa_pass_rate"] if quality else None,
                  "budget_within_envelope": candidate.get("budget", {}).get("within_envelope"),
                  "expense_coverage_complete": not baseline["missing_expense_categories"] and not candidate["missing_expense_categories"]}
    supported = all(value is True for value in safeguards.values())
    return {"currency": candidate["currency"], "baseline_net_per_day": str(before),
            "candidate_net_per_day": str(after), "incremental_net_per_day": str(after-before),
            "incremental_roi_pct": str((after-before)*100/cost_after) if cost_after else None,
            "cost_saving_per_day": str(cost_before-cost_after),
            "observed_opportunity_cost_per_day": str(max(Decimal(0), daily(alternative, "observed_net")-after)) if alternative else None,
            "alternative_status": "observed_comparator" if alternative else "unknown_without_observed_alternative",
            "safeguards": safeguards, "recommendation": "review_candidate" if supported and after > before else "retain_baseline_or_collect_missing_evidence",
            "automatically_applied": False, "causal_effect_established": False,
            "limits": "Descriptive daily normalization; workload, risk, strategic value and counterfactual comparability require human review."}


def rubric_score(rubric: Sequence[dict], scores: Mapping[str, object]) -> float:
    names = [r["name"] for r in rubric]
    if not 1 <= len(rubric) <= 12 or len(set(names)) != len(names) or set(scores) != set(names):
        raise ValueError("Exact unique bounded rubric metrics required")
    total, weighted = Decimal(0), Decimal(0)
    for metric in rubric:
        name, maximum, weight = metric["name"], metric_number(metric["maximum"]), metric_number(metric["weight"])
        score = metric_number(scores[name])
        if not 1 <= len(name.strip()) <= 80 or not 0 < maximum <= 1000 or not 0 < weight <= 100 or not 0 <= score <= maximum:
            raise ValueError("Rubric weights, maxima and scores outside bounds")
        total += weight
        weighted += weight*score/maximum
    return float(weighted*100/total)


def summarize_quality(rubric: Sequence[dict], samples: Sequence[dict], *, expected_per_variant: int) -> dict:
    from math import sqrt
    result = {}
    for variant in ("baseline", "candidate"):
        selected = [r for r in samples if r["variant"] == variant]
        values = [rubric_score(rubric, r["scores"]) for r in selected]
        mean = sum(values)/len(values) if values else None
        se = sqrt(sum((v-mean)**2 for v in values)/(len(values)-1)/len(values)) if len(values) > 1 else None
        result[variant] = {"samples": len(values), "expected_samples": expected_per_variant,
                           "pending_samples": max(0, expected_per_variant-len(values)), "mean_score_pct": mean,
                           "descriptive_mean_interval_95": [max(0, mean-1.96*se), min(100, mean+1.96*se)] if se is not None else None}
    before, after = result["baseline"]["mean_score_pct"], result["candidate"]["mean_score_pct"]
    return {**result, "score_delta_pct": after-before if before is not None and after is not None else None,
            "complete": all(result[v]["pending_samples"] == 0 for v in result),
            "measurement": "independently_reviewed_human_rubric", "causal_effect_established": False,
            "limits": "Human-scored source artifacts; small-sample normal intervals are descriptive. Provider/model execution and general superiority are not certified."}


def measurement_series(*, dimension: str, metric: str, unit: str, entity_ref: str) -> dict:
    if dimension not in ("cost", "revenue", "growth", "market", "risk", "headcount") or any(
        not 1 <= len(s.strip()) <= 160 for s in (metric, unit, entity_ref)
    ):
        raise ValueError("Bounded dimension, metric, unit and entity required")
    if dimension in ("cost", "revenue") and (len(unit) != 3 or not unit.isascii() or not unit.isalpha() or not unit.isupper()):
        raise ValueError("Financial series unit must be a three-letter currency")
    if dimension == "risk" and unit != "probability":
        raise ValueError("Risk series requires probability units")
    value = {"dimension": dimension, "metric": metric.strip(), "unit": unit.strip(), "entity_ref": entity_ref.strip()}
    return {**value, "series_key": evidence_digest([value])}


def calibrate_series(predictions: Sequence[dict], observations: Sequence[dict]) -> dict:
    from math import sqrt
    actual = {(o["series_key"], o["period_start"], o["period_end"]): o for o in observations}
    if len(actual) != len(observations):
        raise ValueError("Unique exact-period observations required")
    keys = [(p["series_key"], p["period_start"], p["period_end"]) for p in predictions]
    if len(set(keys)) != len(keys):
        raise ValueError("Unique frozen series-period predictions required")
    groups, paired = {}, []
    for prediction, key in zip(predictions, keys):
        group = groups.setdefault(prediction["series_key"], {"dimension": prediction["dimension"], "metric": prediction["metric"],
            "unit": prediction["unit"], "entity_ref": prediction["entity_ref"], "expected_samples": 0, "errors": [], "covered": []})
        group["expected_samples"] += 1
        observed = actual.get(key)
        if observed is None:
            continue
        if any(observed[k] != prediction[k] for k in ("dimension", "metric", "unit", "entity_ref")):
            raise ValueError("Observation series definition differs from forecast")
        value, center = metric_number(observed["value"]), metric_number(prediction["predicted_value"])
        low, high = metric_number(prediction["lower"]), metric_number(prediction["upper"])
        error = float(center-value)
        group["errors"].append(error)
        group["covered"].append(low <= value <= high)
        paired.append({"series_key": key[0], "period_start": key[1], "period_end": key[2],
                       "prediction": prediction, "observed_value": str(value), "signed_error": error,
                       "observation_id": observed["id"], "observation_digest": observed["digest"]})
    for group in groups.values():
        errors, coverage = group.pop("errors"), group.pop("covered")
        n = len(errors)
        group.update({"observed_samples": n, "pending_samples": group["expected_samples"]-n,
                      "mean_absolute_error": sum(abs(e) for e in errors)/n if n else None,
                      "root_mean_square_error": sqrt(sum(e*e for e in errors)/n) if n else None,
                      "mean_signed_error": sum(errors)/n if n else None,
                      "interval_coverage": sum(coverage)/n if n else None})
    return {"series": groups, "pairs": paired, "observed_samples": len(paired),
            "pending_samples": len(predictions)-len(paired), "accuracy_certified": False,
            "applied": False, "limits": "Held-out exact-period errors on reviewed supplied outcomes; sample counts and interval coverage do not guarantee future accuracy."}


def plan_revision_intent(*, plan_id: str, base_revision: int, title: str,
                         starts_at: datetime, ends_at: datetime,
                         budget_ceiling: str, evidence_ref: str,
                         rationale: str) -> tuple[dict, str]:
    """Immutable, independently reviewed plan amendment identity."""
    from uuid import UUID

    identifier = str(UUID(plan_id))
    if type(base_revision) is not int or base_revision < 1:
        raise ValueError("Valid base planning revision required")
    if not 1 <= len(title.strip()) <= 300:
        raise ValueError("Reviewed title required")
    if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
        raise ValueError("Timezone-aware planning window required")
    if not 1 <= len(evidence_ref.strip()) <= 1024 or not (
        1 <= len(rationale.strip()) <= 2000
    ):
        raise ValueError("Real planning evidence and justification required")
    limit = _amount(budget_ceiling)
    record = {
        "plan_id": identifier, "base_revision": base_revision,
        "title": title.strip(), "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(), "budget_ceiling": str(limit),
        "evidence_ref": evidence_ref.strip(), "rationale": rationale.strip(),
    }
    encoded = dumps(record, sort_keys=True, separators=(",", ":"))
    return record, sha256(encoded.encode("utf-8")).hexdigest()


def organization_change_intent(*, change_kind: str, target_id: str,
                               reason: str, department_id: str | None = None,
                               name: str | None = None,
                               manager_id: str | None = None,
                               role_level: int | None = None) -> tuple[dict, str]:
    """Canonical immutable HR intent, not merely a target-id approval.

    The exact proposed values (including reason) are shown to the independent
    reviewer and checked again at execution. Unexpected/unused fields fail.
    """
    from uuid import UUID

    kind = change_kind.strip()
    target = str(UUID(target_id))
    reason = reason.strip()
    if kind not in {"hired", "promoted", "terminated", "created", "closed"}:
        raise ValueError("Unrecognized organizational action")
    if not 1 <= len(reason) <= 2000:
        raise ValueError("Reason required for independent review")
    dept = str(UUID(department_id)) if department_id else None
    manager = str(UUID(manager_id)) if manager_id else None
    name = name.strip() if name is not None else None
    if kind == "created":
        if not name or not 1 <= len(name) <= 200 or any(
            value is not None for value in (dept, manager, role_level)
        ):
            raise ValueError("Department creation requires name only")
    elif kind == "hired":
        if not dept or not name or not 1 <= len(name) <= 200 or role_level is not None:
            raise ValueError("AI hiring requires department/name, not role promotion")
    elif kind == "promoted":
        if (type(role_level) is not int or not 2 <= role_level <= 5
            or any(value is not None for value in (dept, name, manager))):
            raise ValueError("Promotion must specify only an increased role level")
    elif any(value is not None for value in (dept, name, manager, role_level)):
        raise ValueError("Closure/termination cannot change other organizational fields")
    payload = {
        "change_kind": kind, "target_id": target, "reason": reason,
        "department_id": dept, "name": name, "manager_id": manager,
        "role_level": role_level,
    }
    encoded = dumps(payload, sort_keys=True, separators=(",", ":"))
    return payload, sha256(encoded.encode("utf-8")).hexdigest()


def agent_evidence_intent(*, employee_id: str, kind: str, label: str,
                          value_int: int | None, evidence_ref: str,
                          note: str) -> tuple[dict, str]:
    """Explicitly human-reviewed operational assertions, never privilege grants."""
    from uuid import UUID

    employee = str(UUID(employee_id))
    if kind not in {"skill", "knowledge", "confidence", "risk",
                    "learning", "permission_awareness"}:
        raise ValueError("Unsupported operational evidence type")
    if not 1 <= len(label.strip()) <= 160:
        raise ValueError("Bounded named competence required")
    if not 1 <= len(evidence_ref.strip()) <= 1024 or not (
        1 <= len(note.strip()) <= 2000
    ):
        raise ValueError("Provenance and review note required")
    if kind == "confidence":
        if type(value_int) is not int or not 0 <= value_int <= 100:
            raise ValueError("Confidence needs bounded self-report scale 0-100")
    elif value_int is not None:
        raise ValueError("Only confidence may use numerical observations")
    record = {
        "employee_id": employee, "kind": kind, "label": label.strip(),
        "value_int": value_int, "evidence_ref": evidence_ref.strip(),
        "note": note.strip(),
    }
    encoded = dumps(record, sort_keys=True, separators=(",", ":"))
    return record, sha256(encoded.encode("utf-8")).hexdigest()


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
