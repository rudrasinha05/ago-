"""P1 read-only authorized-task Board/PM diagnostic, no replay or disclosure."""
from __future__ import annotations

from uuid import uuid4

import pytest

from ago import company_engineering_preflight as p


class Cursor:
    def __init__(self, row):
        self.row = row
    def fetchone(self):
        return self.row


class DB:
    def __init__(self, task=None, approval=None, project=None, run=None):
        self.mapping = {
            "ago_governed_tasks": task,
            "ago_approval_requests": approval,
            "ago_founder_intakes": project,
            "ago_agent_runs": run,
        }
        self.commands = []
    def execute(self, query, params=None):
        self.commands.append(query.strip())
        assert query.lstrip().startswith("SELECT")
        found = next(k for k in self.mapping if k in query)
        return Cursor(self.mapping[found])


def test_no_task_is_readonly_scoped_and_does_not_claim():
    task_id, tenant, founder = (str(uuid4()) for _ in range(3))
    db = DB()
    report = p.inspect_engineering_task(db, tenant_id=tenant,
                                        founder_id=founder, task_id=task_id)
    assert report["task_exists"] is False
    assert report["blocking_checks"] == ["task_not_found_for_founder_tenant"]
    assert report["task_post_authorized"] is False
    assert all(cmd.startswith("SELECT") for cmd in db.commands)


@pytest.mark.parametrize("approval_status,expected", [
    ("approved", True), ("pending", False), ("denied", False),
])
def test_approval_status_is_independent_from_waiting_task_state(
    monkeypatch, approval_status, expected,
):
    tenant, founder, task_id = (str(uuid4()) for _ in range(3))
    db = DB(
        task={"action":"internal:brief", "status":"waiting_approval",
              "approval_id":str(uuid4()), "assignee_id":str(uuid4())},
        approval={"action":"internal:brief", "status":approval_status},
        project={"id":str(uuid4())},
    )
    class Assignments:
        def __init__(self, db):
            self.db = db
        def assignments(self, **_):
            return [{"role": role, "employee_id": str(uuid4())}
                    for role in ("ceo", "cto", "finance", "risk", "quality", "pm",
                                 "employee")]
    monkeypatch.setattr(p, "CompanyOllamaChainQueries", Assignments)
    report = p.inspect_engineering_task(db, tenant_id=tenant,
                                        founder_id=founder, task_id=task_id)
    assert report["task_status"] == "waiting_approval"
    assert report["linked_matching_approval"] is expected
    assert report["seven_employee_hierarchy_verified"]
    assert ("matching_approval_not_approved" in report["blocking_checks"]) is not expected
    assert report["database_modified"] is False
    assert report["task_post_authorized"] is False


def test_missing_board_maps_to_safe_fixable_code(monkeypatch):
    tenant, founder, task_id = (str(uuid4()) for _ in range(3))
    db = DB(
        task={"action":"internal:brief", "status":"waiting_approval",
              "approval_id":str(uuid4()), "assignee_id":str(uuid4())},
        approval={"action":"internal:brief", "status":"approved"},
        project={"id":str(uuid4())},
    )
    class NoBoard:
        def __init__(self, db):
            self.db = db
        def assignments(self, **_):
            raise PermissionError("Founder must appoint all required real AI Board seats")
    monkeypatch.setattr(p, "CompanyOllamaChainQueries", NoBoard)
    result = p.inspect_engineering_task(db, tenant_id=tenant,
                                        founder_id=founder, task_id=task_id)
    assert "board_appointments_incomplete" in result["blocking_checks"]
    assert not result["seven_employee_hierarchy_verified"]
    assert not result["checked_preconditions_pass"]


def test_run_found_never_claims_retry_safe():
    tenant, founder, task_id = (str(uuid4()) for _ in range(3))
    db = DB(
        task={"action":"internal:brief", "status":"failed",
              "approval_id":None, "assignee_id":str(uuid4())},
        run={"status":"failed", "failure_code":"handler_error"},
    )
    result = p.inspect_engineering_task(db, tenant_id=tenant,
                                        founder_id=founder, task_id=task_id)
    assert result["execution_attempted"]
    assert result["latest_run_failure_code"] == "handler_error"
    assert "prior_run_found_do_not_replay" in result["blocking_checks"]
    assert "calendar_at_dispatch_time" in result["unverified_execution_gates"]
    assert result["task_post_authorized"] is False


def test_no_founder_private_details_in_diagnostic(monkeypatch):
    tenant, founder, task_id = (str(uuid4()) for _ in range(3))
    db = DB(
        task={"action":"internal:brief", "status":"waiting_approval",
              "approval_id":str(uuid4()), "assignee_id":str(uuid4())},
        approval={"action":"internal:brief", "status":"approved"},
        project={"id":str(uuid4()), "brief": "PRIVATE_PROJECT_CONTENT"},
    )
    class BrokenBoard:
        def __init__(self, db):
            self.db = db
        def assignments(self, **_):
            raise PermissionError("PRIVATE_LEAK error not in approved list")
    monkeypatch.setattr(p, "CompanyOllamaChainQueries", BrokenBoard)
    report = p.inspect_engineering_task(db, tenant_id=tenant,
                                        founder_id=founder, task_id=task_id)
    assert "PRIVATE_LEAK" not in str(report)
    assert "PRIVATE_PROJECT_CONTENT" not in str(report)
    assert "company_hierarchy_not_verified" in report["blocking_checks"]
