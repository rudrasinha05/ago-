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
    def __init__(self, *, active=True, board=True, existing_role=False):
        self.active, self.board, self.existing_role = active, board, existing_role
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
                {"stage":"discovery","position":1,"suggested_assignee_id":uuid4()},
                {"stage":"architecture","position":2,"suggested_assignee_id":None},
                {"stage":"implementation","position":3,"suggested_assignee_id":None},
            ])
        if "FROM ago_employees" in sql:
            return Cursor([{"role":"software developer"}] if self.existing_role else [])
        raise AssertionError("Unreviewed staffing query")


def person():
    return SimpleNamespace(tenant_id=str(uuid4()),subject=str(uuid4()),
                           roles=("founder",))


def test_ceo_accountable_staffing_proposals_use_only_actual_unassigned_stages():
    actor=person()
    db=DB(existing_role=True)
    result=CompanyChat(db).staffing_proposals(actor,str(uuid4()))
    assert result["kind"]=="ago_p1_readonly_staffing_proposals"
    assert len(result["proposals"])==2
    assert [p["suggested_role"] for p in result["proposals"]]==[
        "Solution Architect", "Software Developer"]
    assert result["proposals"][1]["decision"]=="review_existing_staff"
    assert result["charter_granted"] is False
    assert result["personnel_hired"] is False
    assert result["permission_granted"] is False
    assert result["requires_founder_review"] is True
    assert len(result["source_sha256"])==64
    assert all(actor.tenant_id in str(args) for _,args in db.calls)


def test_draft_projects_unappointed_ceo_and_untrusted_actor_fail_without_writes():
    for options in ({"active":False},{"board":False}):
        db=DB(**options)
        with pytest.raises(PermissionError):
            CompanyChat(db).staffing_proposals(person(),str(uuid4()))
        assert all("INSERT" not in query for query,_ in db.calls)
    db=DB()
    actor=person()
    actor.roles=("reviewer",)
    with pytest.raises(PermissionError):
        CompanyChat(db).staffing_proposals(actor,str(uuid4()))
    assert db.calls==[]
