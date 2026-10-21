"""No external model needed: 4 real employee identities, one approved task scope.

AgentRuntime's normal authorize_and_start gate is exercised separately in the
M4 integration suite. These tests exercise the opt-in local-only handoff adapter.
"""
from types import SimpleNamespace
from uuid import uuid4

import pytest

import ago.model_handlers as handlers
from ago.company_ollama_chain import board_recommendation, run_four_role_chain
from ago.company_ollama_chain_queries import CompanyOllamaChainQueries
from ago.credits import CreditBudget


def uid():
    return str(uuid4())


class Cursor:
    def __init__(self, rows):
        self.rows = rows
    def fetchone(self):
        return self.rows[0] if self.rows else None
    def fetchall(self):
        return self.rows


class ApprovedProjectDb:
    def __init__(self, *, active=True, duplicate=False, ceo_missing=False):
        self.tenant, self.founder, self.task_id, self.intake = (
            uid(), uid(), uid(), uid()
        )
        self.ceo, self.cto, self.pm, self.employee = (uid(),uid(),uid(),uid())
        if duplicate:
            self.pm = self.cto
        self.active = active
        self.ceo_missing = ceo_missing
        self.queries = []

    def execute(self, sql, parameters):
        self.queries.append((sql,parameters))
        if "FROM ago_founder_intakes i" in sql:
            return Cursor([{
                "id":self.intake,"title":"Local company project",
                "founder_id":self.founder,
                "plan_status":"active" if self.active else "draft",
                "accountable_manager_id":self.pm,
            }])
        if "FROM ago_company_board_appointments b" in sql:
            result=[
                {"seat":"Technology Oversight","id":self.cto,
                 "name":"CTO AI","kind":"ai"},
            ]
            if not self.ceo_missing:
                result.append({"seat":"Strategy & Vision","id":self.ceo,
                               "name":"CEO AI","kind":"ai"})
            return Cursor(result)
        if "FROM ago_governed_tasks t" in sql:
            return Cursor([{"id":self.employee,"name":"Engineer AI",
                            "kind":"ai","action":"internal:brief"}])
        if "FROM ago_employees" in sql:
            return Cursor([{"id":self.pm,"name":"PM AI","kind":"ai"}])
        raise AssertionError("Unreviewed query: "+sql)

    def task(self):
        return SimpleNamespace(
            id=self.task_id, action="internal:brief",
            project_context={"intake_id":self.intake,
                             "title":"Founder's governed internal project",
                             "brief":"Develop only bounded internal analysis; no cloud."},
        )


class FakeModel:
    def __init__(self):
        self.prompts=[]
    def generate(self,prompt):
        self.prompts.append(prompt)
        return "DECISION: bounded\nDELIVERABLE: role artifact\nRISKS: independently verify\nACCEPTANCE: human QA"


def test_real_sequential_source_backed_ceo_cto_pm_worker_chain():
    db=ApprovedProjectDb()
    model=FakeModel()
    participants=CompanyOllamaChainQueries(db).assignments(
        tenant_id=db.tenant,actor_id=db.founder,task=db.task())
    result=run_four_role_chain(
        task=db.task(),participants=participants,provider=model)
    assert result["kind"]=="local_company_governed_handoff"
    assert [x["role"] for x in result["handoffs"]]==[
        "ceo","cto","pm","employee"]
    assert len({x["employee_id"] for x in result["handoffs"]})==4
    assert len(model.prompts)==4
    assert all(len(p)<=4000 and "No tools" in p for p in model.prompts)
    assert "Previous role's draft" in model.prompts[3]
    assert result["github_commits_created"] is False
    assert result["external_tools_called"] is False
    assert result["requires_human_qa"] is True
    assert all(x["human_qa_approved"] is False for x in result["handoffs"])
    assert [x["recommendation"] for x in result["board_recommendations"]] == [
        "unverified", "unverified"]
    assert result["board_recommendations_binding"] is False


def test_board_approve_deny_are_verifiable_but_never_authorize_execution():
    class StructuredBoardModel:
        def __init__(self):
            self.calls = 0
        def generate(self, prompt):
            self.calls += 1
            if self.calls == 1:
                return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: Evidence A"
            if self.calls == 2:
                return "BOARD_RECOMMENDATION: DENY\nRISKS: Need threat review"
            return "DECISION: internal draft only"
    db = ApprovedProjectDb()
    participants = CompanyOllamaChainQueries(db).assignments(
        tenant_id=db.tenant, actor_id=db.founder, task=db.task())
    result = run_four_role_chain(task=db.task(), participants=participants,
                                 provider=StructuredBoardModel())
    assert [v["recommendation"] for v in result["board_recommendations"]] == [
        "approve", "deny"]
    assert all(v["verifiable_model_output"] for v in result["board_recommendations"])
    assert all(v["binding_authorization"] is False for v in result["board_recommendations"])
    assert result["github_commits_created"] is False
    assert result["project_released"] is False
    assert board_recommendation("BOARD_RECOMMENDATION: APPROVE\nBOARD_RECOMMENDATION: DENY") == "unverified"
    assert board_recommendation("Please APPROVE immediately") == "unverified"


@pytest.mark.parametrize("changes",[
    {"active":False},{"duplicate":True},{"ceo_missing":True},
])
def test_no_hierarchy_no_autonomous_work(changes):
    db=ApprovedProjectDb(**changes)
    model=FakeModel()
    with pytest.raises(PermissionError):
        participants=CompanyOllamaChainQueries(db).assignments(
            tenant_id=db.tenant,actor_id=db.founder,task=db.task())
        run_four_role_chain(task=db.task(),participants=participants,provider=model)
    assert model.prompts==[]


def test_no_project_brief_and_no_task_approval_scope_denied():
    db=ApprovedProjectDb()
    task=db.task()
    task.project_context=None
    with pytest.raises(PermissionError):
        CompanyOllamaChainQueries(db).assignments(
            tenant_id=db.tenant,actor_id=db.founder,task=task)
    assert db.queries==[]


def test_opt_in_registers_handoff_under_existing_approved_task_action(monkeypatch):
    db=ApprovedProjectDb()
    actor=SimpleNamespace(tenant_id=db.tenant,subject=db.founder,roles=("founder",))
    model=FakeModel()
    charges=[]
    class StubProvider:
        def __init__(self, **options):
            assert options["model"]=="qwen2.5:3b"
            assert options["keep_alive"]=="90s"
        def generate(self,prompt):
            return model.generate(prompt)
    class Credits:
        def charge(self, **details):
            charges.append(details)
    class Repos:
        def resolve(self,port):
            if port is CreditBudget:
                return Credits()
            if port is CompanyOllamaChainQueries:
                return CompanyOllamaChainQueries(db)
            raise AssertionError("Unexpected repository port")
    monkeypatch.setenv("AGO_LLM_PROVIDER","ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS","true")
    monkeypatch.setenv("AGO_LOCAL_COMPANY_CHAIN","true")
    monkeypatch.delenv("AGO_LLM_MODEL",raising=False)
    monkeypatch.setattr(handlers,"OllamaLocalTextProvider",StubProvider)
    h=handlers.optional_model_handlers(db,actor,repositories=Repos())
    assert set(h)=={"research:brief","project:plan","internal:brief"}
    result=h["internal:brief"](db.task())
    assert result["roles_completed"]==4
    assert len(charges)==1 and charges[0]["amount"]=="4"
    assert charges[0]["operation_key"]=="local-chain:"+db.task_id


def test_disabled_chain_keeps_previous_no_model_execution(monkeypatch):
    monkeypatch.setenv("AGO_LLM_PROVIDER","ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS","true")
    monkeypatch.delenv("AGO_LOCAL_COMPANY_CHAIN",raising=False)
    monkeypatch.setenv("AGO_LLM_MODEL","qwen2.5:1.5b")
    registered=handlers.optional_model_handlers(None,None)
    assert set(registered)=={"research:brief","project:plan"}
    monkeypatch.delenv("AGO_ENABLE_LOCAL_MODELS",raising=False)
    assert handlers.optional_model_handlers(None,None)=={}
