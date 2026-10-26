"""Founder delivery overview is a truthful, read-only, tenant-scoped view."""
from uuid import uuid4

import pytest
from fastapi import HTTPException

from ago.api_company_chat import delivery_overview_record, founder_delivery_overview
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee


BASE = "/v1/organization/company"


def test_delivery_overview_requires_signed_founder_permissions(case):
    client, headers, _ = case
    endpoint = BASE + "/projects/delivery-overview"
    assert client.get(endpoint).status_code == 401
    assert client.get(endpoint, headers=headers["reviewer"]).status_code == 403
    response = client.get(endpoint, headers=headers["founder"])
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["projects"] == []
    assert value["read_only"] is True
    assert value["owner_local_docker_or_github_verified"] is False
    assert value["human_approvals_automatically_executed"] is False
    assert client.get(endpoint + "?limit=21", headers=headers["founder"]).status_code == 422


def test_delivery_overview_lists_actual_founder_project_without_fake_delivery(case):
    client, headers, info = case
    founder = headers["founder"]
    dept = department(client, founder)
    employee(client, founder, dept)
    project = post(client, BASE + "/projects/start", founder, {
        "brief": "Build and review a private secure student marks analysis workflow",
        "operation_key": str(uuid4()),
    })
    result = client.get(BASE + "/projects/delivery-overview", headers=founder)
    assert result.status_code == 200, result.text
    records = result.json()["projects"]
    assert len(records) == 1
    row = records[0]
    assert row["project_id"] == project["id"]
    assert row["plan_status"] == "draft"
    assert row["delivery_state"] == "awaiting_project_plan_approval"
    assert row["release_ready"] is False
    assert row["github_commit_verified"] is False
    assert row["docker_qa_verified"] is False
    assert row["draft_pr_verified"] is False
    assert all(stage["qa_verdict"] is None for stage in row["stages"])
    assert all(stage["awaiting_independent_qa"] is False for stage in row["stages"])
    # An unrelated reviewer's own signed identity never grants Founder project access.
    assert client.get(BASE + "/projects/delivery-overview",
                      headers=headers["reviewer"]).status_code == 403


def test_delivery_status_prefers_failure_or_missing_qa_over_running():
    identifier = str(uuid4())
    base = {"id": identifier}
    details = {
        "id": identifier, "title": "Real project", "plan_status": "active",
        "accountable_manager_name": "AI CEO",
        "stages": [
            {"stage": "implementation", "position": 1,
             "task_status": "running", "qa_verdict": None,
             "agent_run_status": "running", "executing_employee": "AI engineer"},
            {"stage": "quality", "position": 2,
             "task_status": "completed", "qa_verdict": None,
             "agent_run_status": "completed"},
        ],
    }
    row = delivery_overview_record(base, details, [])
    assert row["delivery_state"] == "waiting_for_independent_qa"
    assert row["stages"][1]["awaiting_independent_qa"] is True
    assert row["stages"][0]["employee"] == "AI engineer"
    assert row["release_ready"] is False
    details["stages"].append({
        "stage": "release", "position": 3, "task_status": "failed",
        "qa_verdict": "fail",
    })
    assert delivery_overview_record(base, details, [])["delivery_state"] == "blocked"
    details["stages"][-1]["qa_verdict"] = "unknown"
    with pytest.raises(ValueError, match="Unrecognized QA"):
        delivery_overview_record(base, details, [])
    with pytest.raises(ValueError, match="differ"):
        delivery_overview_record({"id": str(uuid4())}, details, [])


def test_delivery_overview_does_not_mix_other_project_approvals():
    from types import SimpleNamespace
    from unittest.mock import Mock
    id1, id2 = str(uuid4()), str(uuid4())
    t1 = str(uuid4())
    store = Mock()
    store.projects.return_value = [{"id": id1, "title": "One"}]
    store.project_details.return_value = {
        "id": id1, "title": "One", "plan_status": "active",
        "stages": [{"stage": "implementation", "position": 1,
                    "task_id": t1, "task_status": "proposed",
                    "qa_verdict": None}],
    }
    store.approval_inbox.return_value = [
        {"id": "a1", "founder_intake_id": id1, "status": "pending"},
        {"id": "a2", "founder_intake_id": id2, "status": "pending"},
        {"id": "a3", "task_id": t1, "status": "pending"},
        {"id": "a4", "task_id": t1, "status": "approved"},
        {"id": "a5", "task_id": str(uuid4()), "status": "pending"},
    ]
    repos = Mock()
    repos.resolve.return_value = store
    actor = SimpleNamespace(tenant_id=str(uuid4()), subject=str(uuid4()))
    result = founder_delivery_overview(limit=20, offset=0,
                                       actor=actor, repositories=repos)
    assert [a["approval_id"] for a in result["projects"][0]["pending_approvals"]] == [
        "a1", "a3"
    ]
    store.projects.assert_called_once_with(actor.tenant_id, 20, 0,
                                           reader_id=actor.subject)
    store.project_details.assert_called_once_with(actor.tenant_id, id1,
                                                   reader_id=actor.subject)
    # RBAC helper is also exercised by the signed HTTP integration test above.


def test_delivery_overview_rejects_missing_source_records_instead_of_fake_success():
    from types import SimpleNamespace
    from unittest.mock import Mock
    id1 = str(uuid4())
    store = Mock()
    store.projects.return_value = [{"id": id1}]
    store.project_details.return_value = {"id": id1, "stages": None}
    store.approval_inbox.return_value = []
    repos = Mock()
    repos.resolve.return_value = store
    actor = SimpleNamespace(tenant_id=str(uuid4()), subject=str(uuid4()))
    with pytest.raises(HTTPException) as exc:
        founder_delivery_overview(limit=20, offset=0,
                                  actor=actor, repositories=repos)
    assert exc.value.status_code == 400
