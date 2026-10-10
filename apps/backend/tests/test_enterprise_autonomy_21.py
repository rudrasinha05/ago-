"""Section 21: evaluated autonomy scores are advisory; no self-granted permission."""
from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, post


def test_unreviewed_employee_stays_tier_zero(case):
    client, headers, _ = case
    founder = headers["founder"]
    worker = employee(client, founder, department(client, founder))
    endpoint = f"/v1/operations/enterprise/agents/{worker}/autonomy"
    response = client.get(endpoint, headers=founder)
    assert response.status_code == 200
    evidence = response.json()
    assert evidence["reviewed_task_samples"] == 0
    assert evidence["advisory_autonomy_tier"] == 0
    assert evidence["observed_pass_rate_pct"] is None
    assert evidence["delegation_granted"] is False
    assert evidence["task_approval_required"] is True
    assert evidence["human_escalation"] == "independent_reviewer"
    assert evidence["subjective_consciousness"] is False
    assert client.get(endpoint).status_code == 401


def test_blocking_help_prevents_advisory_autonomy_even_when_employee_exists(case):
    client, headers, _ = case
    founder = headers["founder"]
    worker = employee(client, founder, department(client, founder))
    post(client, "/v1/operations/enterprise/assistance", founder, {
        "employee_id": worker, "reason": "missing_permission",
        "severity": "blocking", "task_id": None,
        "summary": "Sensitive action requires independent human review",
        "evidence_ref": "policy:human-review-required",
    })
    state = client.get(
        f"/v1/operations/enterprise/agents/{worker}/autonomy", headers=founder,
    ).json()
    assert state["advisory_autonomy_tier"] == 0
    assert state["has_active_blocking_escalations"]
    assert state["delegation_granted"] is False
