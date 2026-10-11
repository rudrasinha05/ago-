# Section28 — source-grounded architectural comparison

Reviewed2026-10-11 against original28.1–28.12, master version14 and0073346.
The original describes **architectural scope**, not a feature-parity or performance
ranking. AGO's intended first-class unit is a governed organization. The current
product is a personal-localhost modular monolith executing approved, allowlisted
work. Full enterprise graph, psychology, analytics and partner platform remain
separate sections. Those intentions are not shipped capability or competitive proof.

## Framework comparison

| System and primary reference | Documented overlap | AGO-specific application contract and limit |
|---|---|---|
|[CrewAI Flows](https://docs.crewai.com/v1.15.27/en/concepts/flows), [human feedback](https://docs.crewai.com/v1.15.27/en/learn/human-feedback-in-flows)|Event-driven flow state, branching, persistence and human feedback. AMP additionally supplies managed deployment, observability and tool reuse.|AGO combines durable employee/department identity, exact independent review, per-task QA, budgets, constitutional controls, planning and one-way Twin evidence in one application. This does not establish that CrewAI cannot implement those contracts, or that AGO is more capable at agent work.|
|[Microsoft AutoGen](https://microsoft.github.io/autogen/stable/index.html), [HITL](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/human-in-the-loop.html), [memory](https://microsoft.github.io/autogen/dev/user-guide/agentchat-user-guide/memory.html)|Core, AgentChat and extensions provide agent messaging, teams, tools, user feedback, state and extensible memory. Current documentation points new projects toward Microsoft Agent Framework.|AGO's system of record is its tenant-scoped approvals, tasks, QA, policy versions and audits. Conversations can supply evidence; they do not confer authority. AutoGen applications can add organizational policy, so no absence or universal safety claim is made.|
|[LangGraph overview](https://docs.langchain.com/oss/python/langgraph/overview), [interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [persistence](https://docs.langchain.com/oss/python/langgraph/persistence)|Stateful graph execution, checkpoints, interrupts/HITL, memory and fault recovery are native capabilities.|Graph state/interrupts and organizational identity/authority are different contracts. The native graph experiment below shows both the overlap and use of AGO as an application boundary. LangGraph is not inherently ungoverned; the app author chooses enforcement.|
|[OpenHands security](https://docs.openhands.dev/sdk/guides/security), [sandbox](https://docs.openhands.dev/openhands/usage/advanced/custom-sandbox-guide)|Software-engineering agents, workspace/sandbox execution, confirmation policies and risk analysis. Approval is configurable; external actions can be rejected.|AGO's intent spans cross-functional departments and organization-level review/economics/simulation. Current AGO uses bounded trusted handlers and does not reproduce unrestricted software engineering. Sandbox and security controls are overlapping concerns, not an AGO invention.|

## Business software comparison

| Representative source | Actual overlap | Scope distinction, not superiority |
|---|---|---|
|[Camunda human tasks](https://docs.camunda.io/docs/8.8/guides/orchestrate-human-tasks/), [agentic orchestration](https://docs.camunda.io/docs/8.7/components/agentic-orchestration/), [AI agent connector](https://docs.camunda.io/docs/components/connectors/out-of-the-box-connectors/agentic-ai-aiagent/)|BPMN process/user tasks, events, incidents/retries, connectors and AI-driven agentic orchestration.|AGO specifies employee lifecycle and constitutional/economic/memory feedback around work. Modern BPM can orchestrate AI and human governance; describing all BPM as fixed and nonintelligent would be inaccurate. No native Camunda benchmark was run.|
|[Odoo planning](https://www.odoo.com/documentation/18.0/applications/services/planning.html), [project](https://www.odoo.com/documentation/19.0/applications/services/project.html), [project dashboard](https://www.odoo.com/documentation/19.0/applications/services/project/project_management/project_dashboard.html)|Projects, employee shifts/availability, accounting-linked budgets, time and profitability dashboards.|AGO's quota and reviewed economics measure approved AI work; they are not an accounting/ERP replacement or audited business profit. Proposed ERP integration still needs Section34. No native Odoo benchmark was run.|
|[Jira features](https://www.atlassian.com/software/jira/features)|Planning, workflows, automation, security, capacity/performance metrics and Rovo AI analysis are documented.|AGO attempts to operate approved work and retain organizational learning rather than only represent tasks. Jira also automates work and uses AI; universal claims that project tools only track tickets are unsupported. No native Jira benchmark was run.|

## Organization-level governance

Persistent tenant and employee identities determine who owns work. Strategy/planning
determine why it exists. Independent exact-action approval controls permission to
start; a separate human QA decision controls acceptance. The Constitution can block
new operations across registered contexts, including an otherwise approved task.
Economic/quality/Twin records preserve evidence and uncertainty rather than grant
authority. Meta Brain proposes; it does not silently deploy. These combined
application contracts explain original28.1–28.11 without inventing universal
framework limitations. Existing evidence paths are listed in the claim catalog.

## Reproducible comparative experiment

Install the isolated lab lock and backend development/PostgreSQL extras into a
disposable environment. Apply the repo's checksum migrations to a disposable local
database, set AGO_TEST_POSTGRES_DSN, then from apps/backend run:

```bash
python -m pip install -r tests_comparative/requirements.txt
python -m pytest -q -s tests_comparative tests/test_section28_comparison.py
```

The same native LangGraph1.2.13 StateGraph runs a fixed local operation, first as
an unmediated **test application**, then through the actual AGO signed HTTP task
boundary. Both arms invoke the same `ago.agent_handlers.internal_brief` function
with the same immutable task identity; the independently approved arm must produce
the identical output. The input and graph topology are controlled. Tested factors:
missing approval, independent approval, constitutional containment, foreign tenant
and single execution. A separate actual checkpoint/interrupt/resume experiment
demonstrates LangGraph's own human-feedback capability. No provider/model/API key,
external tool, CrewAI/AutoGen/OpenHands runtime or simulated competitor adapter is used.
The unmediated application's choices are not LangGraph's default safety policy.

The CI lab prints structured arm outcomes, exact installed dependency versions and
graph/library version; its artifact includes decoded output and dependency freeze.
Cases evaluate **where application authority is enforced**, not speed, cost, LLM
quality or production safety. Native framework-wide superiority remains untested.
Source URLs/versions are reviewed separately; the offline catalog checker detects
invalid evidence paths, unsupported claim kinds and source/coverage drift. It cannot
certify that a remote site has not changed since review. Re-review references before
external publication or extending a claim. Fixed primary-source review and actual
native/runtime tests supply reproducible evidence for the narrow architectural claims.

## Original source crosswalk

28.1/28.2 positioning/summary: tables and organization contract above.
28.3 CrewAI,28.4 AutoGen,28.5 LangGraph,28.6 OpenHands: framework table.
28.7 BPM,28.8 ERP,28.9 project management: business table.
28.10 framework building blocks and28.11 organizational thesis: contract/limits.
28.12 source grounding: the original four primary documentation sites plus their
current capability references. Original source is preserved; broad aspirational
statements are qualified using current source evidence rather than treated as facts.
