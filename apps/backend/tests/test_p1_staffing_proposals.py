"""Scoped P1 CEO-backed staffing suggestions never create employees or privileges."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ago.company_chat import CompanyChat


class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class DB:
    def __init__(self, *, active=True, board=True, existing_role=False,
                 activated_stage=None):
        self.active, self.board, self.existing_role = active, board, existing_role
        self.activated_stage = activated_stage
        self.calls = []
        self.hired = False
    def execute(self, sql, args):
        self.calls.append((sql, args))
        assert sql.strip().upper().startswith("SELECT")
        if "FROM ago_founder_intakes i" in sql:
            return Cursor([{"id":uuid4(), "title":"Approved pilot",
                            "status":"active" if self.active else "draft"}])
        if "FROM ago_company_board_appointments b" in sql:
            return Cursor([{"id":uuid4()}] if self.board else [])
        if "FROM ago_founder_intake_stages" in sql:
            return Cursor([
                {"stage":"discovery","position":1,"suggested_assignee_id":uuid4(),
                 "approved_assignee_id":None},
                {"stage":"architecture","position":2,"suggested_assignee_id":None,
                 "approved_assignee_id":uuid4() if self.activated_stage=="architecture" else None},
                {"stage":"implementation","position":3,"suggested_assignee_id":None,
                 "approved_assignee_id":uuid4() if self.activated_stage=="implementation" else None},
            ])
        if "FROM ago_employees e" in sql:
            return Cursor([{"id":uuid4(),"name":"Software Developer",
                            "role_title":"Software Developer"}]
                          if self.existing_role else [])
        if "FROM ago_founder_project_lead" in sql:
            return Cursor([{"accountable_manager_id":uuid4()}])
        raise AssertionError("Unreviewed staffing query")


def person():
    return SimpleNamespace(tenant_id=str(uuid4()),subject=str(uuid4()),
                           roles=("founder",))


def staffing(db):
    return CompanyChat(db)


def test_ceo_accountable_staffing_proposals_use_only_actual_unassigned_stages():
    actor=person()
    db=DB(existing_role=True)
    result=staffing(db).staffing_proposals(actor,str(uuid4()))
    assert result["kind"]=="ago_p1_readonly_staffing_proposals"
    assert len(result["proposals"])==2
    assert [p["suggested_role"] for p in result["proposals"]]==[
        "Solution Architect", "Software Developer"]
    assert result["proposals"][1]["decision"]=="review_existing_staff"
    assert result["proposals"][1]["eligible_existing_count"]==1
    assert result["proposals"][1]["eligible_candidates"][0]["employee_name"]=="Software Developer"
    assert not result["proposals"][0]["eligible_candidates"]
    assert result["charter_granted"] is False
    assert result["personnel_hired"] is False
    assert result["permission_granted"] is False
    assert result["requires_founder_review"] is True
    assert result["eligible_employee_ids"]
    assert all(isinstance(identifier,str) for identifier in result["eligible_employee_ids"])
    assert len(result["source_sha256"])==64
    assert all(actor.tenant_id in str(args) for _,args in db.calls)


def test_draft_projects_unappointed_ceo_and_untrusted_actor_fail_without_writes():
    for options in ({"active":False},{"board":False}):
        db=DB(**options)
        with pytest.raises(PermissionError):
            staffing(db).staffing_proposals(person(),str(uuid4()))
        assert all("INSERT" not in query for query,_ in db.calls)
    db=DB()
    actor=person()
    actor.roles=("reviewer",)
    with pytest.raises(PermissionError):
        staffing(db).staffing_proposals(actor,str(uuid4()))
    assert db.calls==[]


def test_readonly_staffing_proposals_do_not_reopen_reviewed_assignment():
    db=DB(existing_role=True,activated_stage="implementation")
    result=staffing(db).staffing_proposals(person(),str(uuid4()))
    assert [item["stage"] for item in result["proposals"]]==["architecture"]
    assert result["charter_granted"] is False
    assert result["personnel_hired"] is False
    assert all(sql.strip().upper().startswith("SELECT") for sql,_ in db.calls)


def test_readonly_specialist_query_filters_terminated_and_closed_workers():
    db=DB(existing_role=True)
    staffing(db).staffing_proposals(person(),str(uuid4()))
    sql=next(query for query,_ in db.calls if "FROM ago_employees e" in query)
    assert "h.change_kind='terminated'" in sql
    assert "d.action='closed'" in sql
    assert "h.tenant_id=e.tenant_id" in sql
    assert "d.tenant_id=e.tenant_id" in sql


def test_quality_suggestion_excludes_implementer_and_project_manager():
    actor=person()
    class GuardedDb(DB):
        def __init__(self):
            super().__init__()
            self.worker=uuid4()
            self.qa=uuid4()
        def execute(self,sql,args):
            if "FROM ago_founder_intake_stages" in sql:
                self.calls.append((sql,args))
                return Cursor([
                    {"stage":"implementation","position":1,
                     "suggested_assignee_id":self.worker,
                     "approved_assignee_id":None},
                    {"stage":"quality","position":2,"suggested_assignee_id":None,
                     "approved_assignee_id":None},
                ])
            if "FROM ago_founder_project_lead" in sql:
                self.calls.append((sql,args))
                return Cursor([{"accountable_manager_id":self.qa}])
            if "FROM ago_employees e" in sql:
                self.calls.append((sql,args))
                return Cursor([
                    {"id":self.worker,"name":"QA Developer","role_title":"QA Engineer"},
                    {"id":self.qa,"name":"QA Manager","role_title":"QA Specialist"},
                    {"id":uuid4(),"name":"Independent QA","role_title":"QA Engineer"},
                ])
            return super().execute(sql,args)
    result=staffing(GuardedDb()).staffing_proposals(actor,str(uuid4()))
    quality=result["proposals"][0]
    assert quality["stage"]=="quality"
    assert quality["eligible_existing_count"]==1
    assert quality["eligible_candidates"][0]["employee_name"]=="Independent QA"
