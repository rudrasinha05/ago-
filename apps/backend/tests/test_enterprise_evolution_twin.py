"""Sections 26-27: human-reviewed evolution and observational twin comparisons.

No synthetic ROI, automated code promotion, external production mutation or
claim of calibrated business predictions.
"""
from uuid import uuid4

from test_m7_http_postgres import case as case, decide, post


def test_evolution_observation_requires_independent_review_and_rollback_evidence(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    snapshot = post(client, "/v1/meta/snapshots", founder)
    sample = post(client, "/v1/operations/enterprise/evolution/compare", founder, {
        "snapshot_id": snapshot["id"], "baseline": ["10", "20"],
        "candidate": ["11", "19"],
        "evidence": [{"qa_record": "first"}, {"qa_record": "second"}],
    })
    url = "/v1/operations/enterprise/evolution/" + sample["id"]
    approval = post(client, url + "/approval", founder)
    payload = {"approval_id": approval["approval_id"], "decision": "endorsed",
               "rollback_plan": "Revert through existing independent release gate",
               "evidence_ref": "evaluation:two-reviewed-samples"}
    post(client, url + "/review", founder, payload, expected=403)
    decide(client, reviewer, approval["approval_id"])
    result = post(client, url + "/review", founder, payload)
    assert result["applied"] is False and result["decision"] == "endorsed"
    assert post(client, url + "/review", founder, payload)["idempotent"]
    post(client, url + "/review", founder,
         {**payload, "rollback_plan": "Tampered"}, expected=403)
    history = client.get("/v1/operations/enterprise/evolution/reviews",
                         headers=founder).json()
    assert history[0]["decision"] == "endorsed"
    assert client.get("/v1/operations/enterprise/evolution/reviews").status_code == 401


def test_digital_twin_outcome_is_descriptive_only_and_follows_real_snapshot(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    base = post(client, "/v1/meta/snapshots", founder)
    scenario = post(client, "/v1/operations/enterprise/twin", founder, {
        "snapshot_id": base["id"], "actions": 3,
        "cost_per_action": "2", "budget": "100", "failure_pct": 20,
    })
    after = post(client, "/v1/meta/snapshots", founder)
    endpoint = ("/v1/operations/enterprise/twin/" + scenario["id"]
                + "/compare/" + after["id"])
    approval = post(client, endpoint + "/approval", founder)
    body = {"approval_id": approval["approval_id"],
            "rationale": "Observed QA facts from later executive snapshot"}
    post(client, endpoint, founder, body, expected=403)
    decide(client, reviewer, approval["approval_id"])
    result = post(client, endpoint, founder, body)
    assert result["calibration"] == "descriptive_only"
    assert result["applied"] is False
    assert result["observed_completed_task_delta"] == 0
    assert post(client, endpoint, founder, body)["idempotent"] is True
    past = client.get("/v1/operations/enterprise/twin/comparisons",
                      headers=founder).json()
    assert past[0]["outcome"]["calibration"] == "descriptive_only"
    # Simulating from the current future cannot be compared to a previous
    # evidence snapshot, even when the reviewer accepts the request.
    wrong_endpoint = ("/v1/operations/enterprise/twin/" + scenario["id"]
                      + "/compare/" + base["id"])
    bad = post(client, wrong_endpoint + "/approval", founder)
    decide(client, reviewer, bad["approval_id"])
    post(client, wrong_endpoint, founder,
         {"approval_id": bad["approval_id"], "rationale": "Stale baseline"},
         expected=400)
    assert client.get("/v1/operations/enterprise/twin/comparisons").status_code == 401
