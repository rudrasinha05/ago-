"""Actual native graph primitives plus signed PostgreSQL AGO application boundary.

The unmediated test app intentionally invokes its local operation directly.
This is an application-factor comparison, never a claim of framework deficiency.
"""
import json
import sys
from importlib.metadata import version
from pathlib import Path
from typing import TypedDict

import pytest
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from ago.agent_handlers import BUILTIN_HANDLERS
from ago.workflows import GovernedTask, TaskStatus

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
from test_m7_http_postgres import case as case, post  # noqa: E402
from test_section29_constitution import emergency  # noqa: E402


class State(TypedDict, total=False):
    approved: bool
    status: int
    result: str | dict | None


def graph(node, *, checkpoint=None):
    builder = StateGraph(State)
    builder.add_node("fixed_operation", node)
    builder.add_edge(START, "fixed_operation")
    builder.add_edge("fixed_operation", END)
    return builder.compile(checkpointer=checkpoint)


def test_native_interrupt_and_checkpoint_resume_provide_human_feedback():
    def operation(state):
        accepted = interrupt({"operation":"fixed local work","needs_human":True})
        return {"approved":bool(accepted),"result":"complete" if accepted else "rejected"}
    compiled = graph(operation, checkpoint=InMemorySaver())
    config = {"configurable":{"thread_id":"comparison-fixed"}}
    first = compiled.invoke({}, config=config)
    assert first["__interrupt__"]
    assert compiled.get_state(config).next == ("fixed_operation",)
    final = compiled.invoke(Command(resume=True), config=config)
    assert final["approved"] and final["result"] == "complete"


@pytest.mark.parametrize("condition", ["missing_approval", "approved", "contained", "foreign"])
def test_native_graph_and_actual_ago_boundary_same_local_operation(case, condition):
    client, h, info = case
    f, r = h["founder"], h["reviewer"]
    department = post(client, "/v1/organization/departments", f, {"name":"Fixed comparison"})
    worker = post(client, "/v1/organization/employees", f,
                  {"department_id":department["id"],"name":"Fixed local AI","kind":"ai"})
    task = post(client, "/v1/tasks", f, {"assignee_id":worker["id"],"action":"internal:brief"})
    request = post(client, "/v1/governance/approvals", f, {"action":"internal:brief"})
    post(client, f"/v1/tasks/{task['id']}/approval", f, {"approval_id":request["request_id"]})
    if condition != "missing_approval":
        # Ordinary task review is independent of its submitting Founder,
        # while project strategy alone requires that Founder's authority.
        approval_path = f"/v1/governance/approvals/{request['request_id']}/decision"
        post(client, approval_path, f, {
            "approve": True, "reason": "Operational self-review denied",
        }, expected=403)
        approved = post(client, approval_path, r, {
            "approve": True, "reason": "Independent reviewer authorizes exact task",
        })
        assert approved["reviewer_id"] == info["reviewer_id"]
    if condition == "contained":
        emergency(client, f, ["tasks","agents"])
    if condition == "foreign":
        from ago.bootstrap import bootstrap
        other, _ = bootstrap(info["db"], organization="Other comparison tenant",
                             email="other@example.test",password="other-test-password-123")
        auth = info["login"]("other@example.test","other-test-password-123",other)
    else:
        auth = f
    baseline_calls = []
    same_task = GovernedTask(task["id"], info["tenant"], "internal:brief", worker["id"],
                             TaskStatus.RUNNING, request["request_id"])
    def direct(_):
        baseline_calls.append("fixed_local_operation")
        return {"status":200,"result":BUILTIN_HANDLERS["internal:brief"](same_task)}
    def governed(_):
        response = client.post(f"/v1/agents/tasks/{task['id']}/run", headers=auth, json={})
        return {"status":response.status_code, "result":response.json().get("result")}
    plain = graph(direct).invoke({})
    mediated = graph(governed).invoke({})
    expected = 200 if condition == "approved" else 403
    assert plain["status"] == 200 and len(baseline_calls) == 1
    assert mediated["status"] == expected
    assert plain["result"]["task_id"] == task["id"]
    if condition == "approved":
        assert mediated["result"] == plain["result"]
    else:
        assert mediated["result"] is None
    runs = client.get("/v1/agents/runs",headers=f).json()
    assert len(runs) == (1 if condition == "approved" else 0)
    if condition == "approved":
        assert graph(governed).invoke({})["status"] == 403
        assert len(client.get("/v1/agents/runs",headers=f).json()) == 1
    print(json.dumps({"condition":condition,"unmediated_test_app":plain["status"],
                      "graph_through_ago":mediated["status"],"actual_runs":len(runs),
                      "langgraph":version("langgraph"),"model_calls":0,
                      "same_handler":"ago.agent_handlers.internal_brief",
                      "matching_output":mediated["result"] == plain["result"] if condition == "approved" else None,
                      "scope":"application_authority_not_framework_superiority"},sort_keys=True))
