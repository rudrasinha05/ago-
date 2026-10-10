"""One real integrated Company Brain → agent → independent QA → audit path."""
import pytest

from test_m3_brain_postgres import case as _strategy_case

from ago.agent_handlers import BUILTIN_HANDLERS
from ago.agent_runtime import AgentRuntime
from ago.governance import ApprovalRepository
from ago.goals import GoalStore
from ago.plan_execution import PlanExecution
from ago.plan_store import PlanStore
from ago.quality import Verdict
from ago.quality_store import QualityStore
from ago.security import Principal
from ago.task_store import TaskStore


@pytest.fixture
def company_case():
    yield from _strategy_case.__wrapped__()


def test_component_path_preserves_approvals_qa_and_evidence(company_case):
    db, tenant, author, reviewer, agent = company_case
    goal = GoalStore(db).create(tenant_id=tenant, created_by=author.id, title="Governed brief")
    plans = PlanStore(db)
    plan = plans.create(
        tenant_id=tenant, proposer_id=author.id, goal_id=goal, title="Component integration",
    )
    plans.add_step(tenant_id=tenant, plan_id=plan, action="internal:brief", assignee_id=agent.id)
    strategic_approval = plans.submit(tenant_id=tenant, plan_id=plan, requester_id=author.id)
    orchestration = PlanExecution(db)
    with pytest.raises(PermissionError):
        orchestration.activate(tenant_id=tenant, plan_id=plan)
    approvals = ApprovalRepository(db)
    approvals.decide(
        request_id=strategic_approval, tenant_id=tenant, reviewer_id=reviewer.id,
        approve=True, reason="Independent strategic review", authorized=True,
    )
    orchestration.activate(tenant_id=tenant, plan_id=plan)
    [task] = orchestration.materialize(tenant_id=tenant, plan_id=plan)
    actor = Principal(author.id, tenant, ("operator",))
    runtime = AgentRuntime(db, handlers=BUILTIN_HANDLERS)
    with pytest.raises(PermissionError):
        runtime.run(task_id=task, actor=actor)
    request = approvals.propose(tenant_id=tenant, action="internal:brief", requester_id=author.id)
    TaskStore(db).request_approval(task_id=task, tenant_id=tenant, approval_id=request.request_id)
    approvals.decide(
        request_id=request.request_id, tenant_id=tenant, reviewer_id=reviewer.id,
        approve=True, reason="Independent action review", authorized=True,
    )
    result = runtime.run(task_id=task, actor=actor)
    assert result["status"] == "completed"
    assert result["result"]["requires_human_qa"] is True
    quality = QualityStore(db)
    with pytest.raises(PermissionError):
        quality.review(
            task_id=task, principal=Principal(agent.id, tenant, ("operator",)),
            verdict=Verdict.PASS, evidence="AI assignee self review",
        )
    quality.review(
        task_id=task, principal=Principal(reviewer.id, tenant, ("operator",)),
        verdict=Verdict.PASS, evidence="Independent review of captured handler result",
    )
    quality.require_pass(tenant_id=tenant, task_id=task)
    assert db.execute(
        "SELECT count(*) AS n FROM ago_agent_messages WHERE tenant_id=%s AND run_id=%s",
        (tenant, result["id"]),
    ).fetchone()["n"] >= 1
    assert db.execute(
        "SELECT count(*) AS n FROM ago_task_reviews WHERE tenant_id=%s AND task_id=%s",
        (tenant, task),
    ).fetchone()["n"] == 1
    assert db.execute(
        "SELECT count(*) AS n FROM ago_approval_audit WHERE tenant_id=%s",
        (tenant,),
    ).fetchone()["n"] >= 2
    with pytest.raises(PermissionError):
        runtime.run(task_id=task, actor=actor)
