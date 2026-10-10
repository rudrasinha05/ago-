"""Section 22: independent evidence review, nonconsciousness and no privilege granting."""
import pytest

from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post


def test_agent_competence_needs_independent_review_without_self_permissions(case):
    client, headers, context = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dept = department(client, founder)
    worker = employee(client, founder, dept)
    base = f"/v1/operations/enterprise/agents/{worker}/evidence"
    assert client.get(base, headers=founder).json() == []
    proposed = post(client, base + "/approval", founder, {
        "kind": "confidence", "label": "Code task confidence",
        "value_int": 72, "evidence_ref": "qa:human-reported-run-42",
        "note": "Human-reviewed self-report, not calibrated competence",
    })
    intent = proposed["intent_id"]
    assert proposed["review_payload"]["value_int"] == 72
    apply_path = base + "/" + intent + "/apply"
    decision = {"approval_id": proposed["approval_id"]}
    post(client, apply_path, founder, decision, expected=403)
    post(client, "/v1/governance/approvals/" + proposed["approval_id"] + "/decision",
         founder, {"approve": True, "reason": "no self review"}, expected=403)
    decide(client, reviewer, proposed["approval_id"])
    result = post(client, apply_path, founder, decision)
    assert result["permissions_granted"] is False
    assert post(client, apply_path, founder, decision)["idempotent"]
    evidence = client.get(base, headers=founder).json()
    assert len(evidence) == 1 and evidence[0]["value_int"] == 72
    state = client.get(
        f"/v1/operations/enterprise/agents/{worker}/state", headers=founder,
    ).json()
    assert state["confidence"] == 72
    assert state["confidence_calibrated"] is False
    assert state["subjective_consciousness"] is False
    assert state["permission_awareness"] == "requires_runtime_policy_evaluation"
    with pytest.raises(Exception, match="immutable|append.only"):
        with context["db"].transaction():
            context["db"].execute(
                "UPDATE ago_agent_evidence_intents SET label='changed' WHERE tenant_id=%s AND id=%s",
                (context["tenant"], intent),
            )
    assert client.get(base).status_code == 401


def test_agent_learning_references_do_not_issue_privilege(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    worker = employee(client, founder, department(client, founder))
    base = f"/v1/operations/enterprise/agents/{worker}/evidence"
    proposal = post(client, base + "/approval", founder, {
        "kind": "learning", "label": "Reviewed SQL exercise",
        "value_int": None, "evidence_ref": "qa:reviewed-example-23",
        "note": "Recorded review only; no autonomous training or access upgrade",
    })
    decide(client, reviewer, proposal["approval_id"])
    post(client, base + "/" + proposal["intent_id"] + "/apply", founder,
         {"approval_id": proposal["approval_id"]})
    state = client.get(
        f"/v1/operations/enterprise/agents/{worker}/state", headers=founder,
    ).json()
    assert state["learning_evidence"] == ["qa:reviewed-example-23"]
    assert state["confidence"] is None
    assert state["permission_awareness"] == "requires_runtime_policy_evaluation"
    post(client, base + "/approval", founder, {
        "kind": "skill", "label": "SQL", "value_int": 99,
        "evidence_ref": "qa:reviewed-example-23", "note": "Invalid score",
    }, expected=400)
