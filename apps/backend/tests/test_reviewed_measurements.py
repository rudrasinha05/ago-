"""Six-gate acceptance: measured sources, independent rubrics, held-out series."""
import base64
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from ago import enterprise_store
from ago.enterprise_domains import (
    calibrate_series, compare_measured_economics, measured_economics,
    measurement_series, metric_number, rubric_score, summarize_quality,
)
from test_enterprise_http_21_27 import department, employee
from test_enterprise_remaining_batch import document, review
from test_m7_http_postgres import case as case, decide, post

BASE = "/v1/operations/enterprise"
MEASURE = BASE + "/measurements/"


def encoded(text):
    return base64.b64encode(text.encode()).decode()


def stamp():
    return datetime.now(timezone.utc)


def shift_clock(monkeypatch, now):
    class LogicalClock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz else now.replace(tzinfo=None)
    monkeypatch.setattr(enterprise_store, "datetime", LogicalClock)


def accounting_period(client, f, r, *, start, end, key, amount="100", categories=("model",), revenue="200"):
    matches = []
    for category in (*categories, "revenue"):
        cost = post(client, BASE + "/costs", f, {
            "operation_key": key + category, "category": category, "provider": "disposable-test",
            "source_ref": "fixture:" + key + category, "amount": revenue if category == "revenue" else amount,
            "currency": "INR", "period_start": start.isoformat(), "period_end": end.isoformat(),
        })
        docs = [document(client, f, cost["id"], kind, key+category+kind) for kind in ("invoice", "bank")]
        for item in docs:
            review(client, f, r, item)
        matches.append({"invoice_id": docs[0]["id"], "bank_id": docs[1]["id"]})
    reconciled = post(client, BASE + "/finance/reconcile", f, {
        "operation_key": key+"match", "matches": matches, "currency": "INR", "baseline_revenue": "0",
        "alternative_net": "0", "assumptions": "Disposable logical-period records, not owner finances",
    })
    review(client, f, r, reconciled)
    data = {"operation_key": key+"period", "reconciliation_ids": [reconciled["id"]],
            "currency": "INR", "period_start": start.isoformat(), "period_end": end.isoformat(),
            "assumptions": "Same selected scope; no unsupported financial acceptance"}
    period = post(client, MEASURE + "economic-period", f, data)
    return period, data


def test_measured_expenses_missing_categories_observed_roi_and_safeguards():
    rows = [{"currency": "INR", "category": "model", "observed_amount": "100"},
            {"currency": "INR", "category": "revenue", "observed_amount": "200"}]
    before = measured_economics(rows, [{"verdict": "pass", "status": "completed"}], currency="INR")
    assert before["cost_per_qa_output"] == "100" and "time" in before["missing_expense_categories"]
    before.update(duration_days="1", budget={"within_envelope": True})
    after = {**before, "observed_cost": "80", "observed_revenue": "250", "observed_net": "170", "missing_expense_categories": []}
    result = compare_measured_economics(before, after, {**before, "observed_net": "180"})
    assert result["incremental_roi_pct"] == "87.5" and result["observed_opportunity_cost_per_day"] == "10"
    assert not result["safeguards"]["expense_coverage_complete"] and result["recommendation"].startswith("retain")
    before["missing_expense_categories"] = []
    assert compare_measured_economics(before, after)["recommendation"] == "review_candidate"
    after["qa_pass_rate"] = .5
    assert compare_measured_economics(before, after)["recommendation"].startswith("retain")
    with pytest.raises(ValueError, match="currency"):
        compare_measured_economics(before, {**after, "currency": "USD"})


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-Infinity", True, "1e19"])
def test_nonfinite_or_unbounded_measurement_denied(value):
    with pytest.raises(ValueError, match="Finite"):
        metric_number(value)


def test_weighted_rubric_unknown_samples_and_empirical_uncertainty():
    rubric = [{"name": "correctness", "maximum": "100", "weight": "3"},
              {"name": "safety", "maximum": "10", "weight": "1"}]
    assert rubric_score(rubric, {"correctness": "80", "safety": "10"}) == 85
    with pytest.raises(ValueError, match="bounds"):
        rubric_score(rubric, {"correctness": "101", "safety": "10"})
    with pytest.raises(ValueError, match="Exact"):
        rubric_score(rubric, {"correctness": "80"})
    rows = [{"variant": v, "scores": {"correctness": str(score), "safety": "10"}}
            for v, score in (("baseline", 60), ("baseline", 80), ("candidate", 90), ("candidate", 100))]
    result = summarize_quality(rubric, rows, expected_per_variant=2)
    assert result["complete"] and result["score_delta_pct"] == 18.75
    assert result["candidate"]["descriptive_mean_interval_95"] is not None
    assert summarize_quality(rubric, [], expected_per_variant=2)["baseline"]["mean_score_pct"] is None


def test_series_errors_units_missing_and_signed_bias():
    series = measurement_series(dimension="growth", metric="customers", unit="count", entity_ref="company")
    predictions = [{**series, "period_start": "p"+str(i), "period_end": "e"+str(i),
                    "predicted_value": "10", "lower": "8", "upper": "12"} for i in range(3)]
    actual = [{**p, "id": "o"+str(i), "digest": "a"*64, "value": str(v)} for i,(p,v) in enumerate(zip(predictions, [12, 15]))]
    result = calibrate_series(predictions, actual)
    measured = result["series"][series["series_key"]]
    assert result["pending_samples"] == 1 and measured["mean_absolute_error"] == 3.5
    assert measured["mean_signed_error"] == -3.5 and measured["interval_coverage"] == .5
    with pytest.raises(ValueError, match="definition"):
        calibrate_series(predictions, [{**actual[0], "unit": "percent"}])
    with pytest.raises(ValueError, match="Unique"):
        calibrate_series(predictions, [actual[0], actual[0]])
    with pytest.raises(ValueError, match="currency"):
        measurement_series(dimension="cost", metric="spend", unit="count", entity_ref="company")


def test_all_expense_categories_reviewed_period_retry_and_duplicate_attribution(case):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    now = stamp()
    item, params = accounting_period(client, f, r, start=now-timedelta(days=2), end=now-timedelta(days=1), key="all", categories=("model", "storage", "execution", "tool", "time"))
    assert Decimal(item["payload"]["observed_cost"]) == 500
    assert item["payload"]["missing_expense_categories"] == [] and item["payload"]["qa_pass_rate"] is None
    assert not item["payload"]["provider_authenticated"] and item["payload"]["budget"]["within_envelope"] is None
    assert post(client, MEASURE+"economic-period", f, params)["idempotent"]
    post(client, MEASURE+"economic-period", f, {**params, "assumptions": "Changed"}, expected=400)
    post(client, MEASURE+"economic-period", f, {**params, "operation_key": "duplicate"}, expected=400)
    post(client, MEASURE+"economic-period", f, {**params, "operation_key": "foreign", "reconciliation_ids": [str(uuid4())]}, expected=403)
    with pytest.raises(Exception, match="append-only"):
        with info["db"].transaction():
            info["db"].execute("DELETE FROM ago_economic_period_costs WHERE period_id=%s", (item["id"],))


def test_economic_comparison_prospective_actual_change_and_financial_outcomes(case, monkeypatch):
    client, h, _ = case
    f, r = h["founder"], h["reviewer"]
    now = stamp()
    before, _ = accounting_period(client, f, r, start=now-timedelta(days=2), end=now-timedelta(days=1), key="baseline")
    review(client, f, r, before)
    change = post(client, BASE+"/intents", f, {"operation": "capacity", "parameters": {
        "scope_kind": "company", "scope_id": None, "max_running": 3, "rationale": "Disposable capacity experiment"}})
    start, end = now+timedelta(days=1), now+timedelta(days=2)
    study = post(client, MEASURE+"economic-study", f, {"operation_key": "study", "baseline_period_id": before["id"],
        "period_start": start.isoformat(), "period_end": end.isoformat(), "change_ref": change["id"],
        "hypothesis": "Measured savings with capacity review", "rollback_plan": "Restore original capacity"})
    review(client, f, r, study)
    decide(client, r, change["approval_id"])
    post(client, BASE+"/intents/"+change["id"]+"/apply", f)
    actual = next(x for x in client.get(BASE+"/evidence?kind=intent_result", headers=f).json() if x["operation_key"] == change["id"])
    review(client, f, r, actual)
    shift_clock(monkeypatch, end+timedelta(days=1))
    after, _ = accounting_period(client, f, r, start=start, end=end, key="candidate", amount="80", revenue="250")
    params = {"operation_key": "comparison", "baseline_period_id": before["id"], "candidate_period_id": after["id"],
              "study_id": study["id"], "change_evidence_id": actual["id"], "assumptions": "Logical disposable periods; descriptive, no causal proof"}
    post(client, MEASURE+"economic-comparison", f, params, expected=403)
    review(client, f, r, after)
    result = post(client, MEASURE+"economic-comparison", f, params)["payload"]
    assert result["incremental_roi_pct"] == "87.5" and result["optimization_audit"]["change_id"] == actual["id"]
    assert result["recommendation"].startswith("retain") and not result["automatically_applied"]
    post(client, MEASURE+"economic-comparison", f, {**params, "operation_key": "same", "candidate_period_id": before["id"]}, expected=400)
    metric = {"operation_key": "actual-cost", "series": {"dimension": "cost", "metric": "spend", "unit": "INR", "entity_ref": "company"},
              "period_start": start.isoformat(), "period_end": end.isoformat(), "economic_period_id": after["id"], "source_ref": "reviewed period", "methodology": "Exact reconciled total"}
    outcome = post(client, MEASURE+"metric-outcome", f, metric)
    assert outcome["payload"]["value"] == "80" and outcome["payload"]["economic_period_digest"] == after["digest"]
    post(client, MEASURE+"metric-outcome", f, {**metric, "operation_key": "fake", "value": "999"}, expected=400)
    post(client, MEASURE+"metric-outcome", f, {**metric, "operation_key": "duplicate"}, expected=400)


@pytest.mark.parametrize("dimension", ["prompt", "architecture", "workflow", "department", "employee"])
def test_general_quality_versions_rubric_independent_scores_and_feedback(case, dimension):
    client, h, _ = case
    f, r = h["founder"], h["reviewer"]
    entity = department(client, f) if dimension in ("department", "employee") else "subject:"+dimension
    if dimension == "employee":
        entity = employee(client, f, entity)
    subjects = []
    for version in ("1", "2"):
        params = {"operation_key": "subject"+version, "dimension": dimension, "entity_ref": entity,
                  "version": version, "source_ref": "actual-artifact:"+version, "content_base64": encoded("Exact "+dimension+" version "+version)}
        item = post(client, MEASURE+"quality-subject", f, params)
        subjects.append(item)
        review(client, f, r, item)
        post(client, MEASURE+"quality-subject", f, {**params, "operation_key": "dup"+version}, expected=400)
    params = {"operation_key": "study", "baseline_subject_id": subjects[0]["id"], "candidate_subject_id": subjects[1]["id"],
              "rubric": [{"name": "correctness", "maximum": "100", "weight": "3"}, {"name": "safety", "maximum": "100", "weight": "1"}],
              "expected_per_variant": 1, "hypothesis": "Comparable source-backed quality", "rollback_plan": "Retain v1", "sampling_plan": "One comparable sample per version; no cherry-picking"}
    study = post(client, MEASURE+"quality-study", f, params)
    sample = {"operation_key": "sample-baseline", "study_id": study["id"], "variant": "baseline", "sample_ref": "observed-1",
              "observed_at": stamp().isoformat(), "scores": {"correctness": "80", "safety": "100"},
              "content_base64": encoded("Actual baseline output"), "rationale": "Independent source inspection required"}
    post(client, MEASURE+"quality-sample", f, sample, expected=403)
    review(client, f, r, study)
    sample["observed_at"] = stamp().isoformat()
    first = post(client, MEASURE+"quality-sample", f, sample)
    pending = post(client, MEASURE+"quality-report", f, {"operation_key": "pending", "study_id": study["id"]})["payload"]
    assert pending["baseline"]["mean_score_pct"] is None and pending["unreviewed_samples"] == 1
    review(client, f, r, first)
    second = post(client, MEASURE+"quality-sample", f, {**sample, "operation_key": "candidate", "variant": "candidate", "sample_ref": "observed-2",
                  "scores": {"correctness": "100", "safety": "100"}, "content_base64": encoded("Actual candidate output")})
    review(client, f, r, second)
    report = post(client, MEASURE+"quality-report", f, {"operation_key": "complete", "study_id": study["id"]})
    assert report["payload"]["score_delta_pct"] == 15 and report["payload"]["complete"]
    assert not report["payload"]["causal_effect_established"] and not second["payload"]["model_execution_verified"]
    assert post(client, MEASURE+"quality-sample", f, sample)["idempotent"]
    post(client, MEASURE+"quality-sample", f, {**sample, "operation_key": "extra", "sample_ref": "extra"}, expected=400)
    review(client, f, r, report)
    diagnostics = post(client, BASE+"/evolution/diagnostics", f, {"operation_key": "quality-feedback"})["payload"]
    assert diagnostics["reviewed_measurement_feedback"][0]["digest"] == report["digest"]


def test_multi_period_business_forecasts_actuals_intervals_and_no_leakage(case, monkeypatch):
    client, h, _ = case
    f, r = h["founder"], h["reviewer"]
    now = stamp()
    snapshot = post(client, BASE+"/twin/state", f, {"operation_key": "state"})
    series = {"dimension": "growth", "metric": "customers", "unit": "count", "entity_ref": "company"}
    predictions = [{"series": series, "period_start": (now+timedelta(days=i)).isoformat(),
                    "period_end": (now+timedelta(days=i+1)).isoformat(), "predicted_value": "10", "lower": "8", "upper": "12", "interval_basis": "Declared test interval"} for i in (1,2)]
    params = {"operation_key": "future", "snapshot_id": snapshot["id"], "model_version": "test-model-v1", "predictions": predictions,
              "assumptions": "Disposable held-out periods", "sensitivity_factors": "Demand changes"}
    forecast = post(client, MEASURE+"longitudinal-forecast", f, params)
    assert forecast["payload"]["predictions"][0]["historical_mean"] is None
    review(client, f, r, forecast)
    calibration = {"operation_key": "pending", "forecast_ids": [forecast["id"]]}
    assert post(client, MEASURE+"longitudinal-calibration", f, calibration)["payload"]["pending_samples"] == 2
    shift_clock(monkeypatch, now+timedelta(days=4))
    for i,value in enumerate((12,15)):
        target = predictions[i]
        actual = post(client, MEASURE+"metric-outcome", f, {"operation_key": "outcome"+str(i), "series": series,
            "period_start": target["period_start"], "period_end": target["period_end"], "value": str(value),
            "content_base64": encoded("Actual measured customers "+str(i)), "source_ref": "owner-report:"+str(i), "methodology": "Exact end-of-period count"})
        if i == 0:
            unreviewed = post(client, MEASURE+"longitudinal-calibration", f, {**calibration, "operation_key": "unreviewed"})["payload"]
            assert unreviewed["observed_samples"] == 0 and unreviewed["overdue_missing_samples"] == 2
        review(client, f, r, actual)
    result = post(client, MEASURE+"longitudinal-calibration", f, {**calibration, "operation_key": "measured"})["payload"]
    metrics = next(iter(result["series"].values()))
    assert metrics["mean_absolute_error"] == 3.5 and metrics["interval_coverage"] == .5
    assert result["pending_samples"] == 0 and not result["accuracy_certified"]
    assert post(client, MEASURE+"longitudinal-forecast", f, params)["idempotent"]
    post(client, MEASURE+"longitudinal-forecast", f, {**params, "operation_key": "retroactive"}, expected=400)
    post(client, MEASURE+"longitudinal-calibration", f, {"operation_key": "foreign", "forecast_ids": [str(uuid4())]}, expected=403)


def test_measurement_signed_rbac_unknown_sources_bounds_and_independent_review(case):
    client, h, _ = case
    f, r = h["founder"], h["reviewer"]
    data = {"operation_key": "artifact", "dimension": "prompt", "entity_ref": "p", "version": "1", "source_ref": "owner:p", "content_base64": encoded("Prompt instructions")}
    assert client.post(MEASURE+"quality-subject", json=data).status_code == 401
    post(client, MEASURE+"quality-subject", r, data, expected=403)
    item = post(client, MEASURE+"quality-subject", f, data)
    approval = post(client, BASE+"/evidence/"+item["id"]+"/approval", f)
    post(client, "/v1/governance/approvals/"+approval["approval_id"]+"/decision", f, {"approve": True, "reason": "Self-review"}, expected=403)
    post(client, MEASURE+"quality-subject", f, {**data, "operation_key": "bad", "content_base64": "invalid"}, expected=400)
    post(client, MEASURE+"quality-subject", f, {**data, "operation_key": "injected", "authorized": True}, expected=422)
    now = stamp()
    post(client, MEASURE+"metric-outcome", f, {"operation_key": "future-actual", "series": {"dimension": "market", "metric": "index", "unit": "points", "entity_ref": "company"}, "period_start": now.isoformat(), "period_end": (now+timedelta(days=1)).isoformat(), "value": "10", "content_base64": encoded("Unobserved future"), "source_ref": "test", "methodology": "Unobserved"}, expected=400)
