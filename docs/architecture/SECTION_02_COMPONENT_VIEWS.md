# Section 2 — Source-linked High-Level Component Views

Generated from `section02_components.json`; check with
`python scripts/check_component_diagrams.py`. Read the companion
`SECTION_02_HIGH_LEVEL_COMPONENT_DIAGRAM.md` for acceptance and boundaries.

**Legend:** bounded = existing narrow capability; partial = existing foundation
with broader scope outstanding; planned = absent target subsystem.
Solid arrows describe the labelled current relationship, supported by a
source symbol; dotted arrows describe a proposed interaction, never an
implemented call. Relationships can be queries, references or constraints:
these are not an import graph, deployment sequence or autonomous control loop.

## Component catalog

| Component | Capability status | Source symbols |
|---|---|---|
| Company Brain | partial | [GoalStore](../../apps/backend/ago/goals.py); [PlanExecution](../../apps/backend/ago/plan_execution.py) |
| Meta Brain advisory | partial | [MetaBrain.generate](../../apps/backend/ago/meta_brain.py) |
| Executive Council | partial | [CouncilStore.finalize](../../apps/backend/ago/council_store.py) |
| Independent human approval | bounded | [ApprovalRepository.decide](../../apps/backend/ago/governance.py) |
| Versioned DNA thresholds | partial | [GenomeStore](../../apps/backend/ago/organizational_dna.py) |
| Departments | bounded | [OrganizationStore.add_department](../../apps/backend/ago/organization_store.py) |
| Manager relationships | partial | [OrganizationStore.hire](../../apps/backend/ago/organization_store.py) |
| Human / AI employee registry | partial | [Employee](../../apps/backend/ago/organization.py) |
| Internal handoffs | partial | [HandoffStore.transition](../../apps/backend/ago/handoffs.py) |
| Governed task queue / states | partial | [TaskStore.authorize_and_start](../../apps/backend/ago/task_store.py) |
| Full OOS — future | planned | Future scope; no runtime implementation |
| In-process scheduler | partial | [IntervalScheduler](../../apps/backend/ago/scheduler.py) |
| Plan dependency orchestration | partial | [PlanExecution.materialize](../../apps/backend/ago/plan_execution.py) |
| Allowlisted execution | partial | [AgentRuntime.run](../../apps/backend/ago/agent_runtime.py) |
| Private persistent memory | partial | [MemoryStore](../../apps/backend/ago/organization_store.py) |
| Evidence-reviewed knowledge graph | partial | [KnowledgeStore.review](../../apps/backend/ago/knowledge_store.py) |
| Internal calendar | partial | [CalendarStore.respond](../../apps/backend/ago/calendar_store.py) |
| External communications — future | planned | Future scope; no runtime implementation |
| Independent QA | bounded | [QualityStore.review](../../apps/backend/ago/quality_store.py) |
| Approval / review audit evidence | bounded | [ApprovalRepository](../../apps/backend/ago/governance.py); [QualityStore](../../apps/backend/ago/quality_store.py) |
| Deterministic Digital Twin scenarios | partial | [ScenarioSimulator.estimate](../../apps/backend/ago/simulation.py) |
| Eight-workspace Control Center | partial | [register_console](../../apps/backend/ago/console_host.py) |
| Operational scorecards | partial | [Scorecard](../../apps/backend/ago/scorecard.py) |
| FastAPI monolith / routes | bounded | [create_app](../../apps/backend/ago/main.py) |
| Signed sessions / RBAC perimeter | partial | [authenticated](../../apps/backend/ago/api_m2.py); [install_release_perimeter](../../apps/backend/ago/release_security.py) |
| Shared tenant-scoped PostgreSQL | bounded | [db_connection](../../apps/backend/ago/api_m2.py) |
| Durable outbox / leased worker | partial | [EventWorker.run_once](../../apps/backend/ago/event_worker.py) |
| Optional model provider | partial | [ResponsesTextProvider](../../apps/backend/ago/model_provider.py) |
| Docker / migration / recovery tooling | partial | [schema_integrity](../../apps/backend/ago/release_security.py) |

## Company Brain, Meta Brain and Executive Council

```mermaid
flowchart TD
    c_brain["Company Brain (partial)"]
    c_meta["Meta Brain advisory (partial)"]
    c_council["Executive Council (partial)"]
    c_approval["Independent human approval (bounded)"]
    c_dna["Versioned DNA thresholds (partial)"]
    c_brain -->|"submit / activate approved plans"| c_approval
    c_meta -->|"submit advisory proposals for review"| c_approval
    c_council -->|"quorum then second human approval"| c_approval
    c_meta -->|"evaluate threshold evidence"| c_dna
```

| Relationship | Meaning | Evidence |
|---|---|---|
| brain → approval | submit / activate approved plans | [PlanExecution.activate](../../apps/backend/ago/plan_execution.py) |
| meta → approval | submit advisory proposals for review | [MetaBrain.generate](../../apps/backend/ago/meta_brain.py) |
| council → approval | quorum then second human approval | [CouncilStore.finalize](../../apps/backend/ago/council_store.py) |
| meta → dna | evaluate threshold evidence | [MetaBrain.generate](../../apps/backend/ago/meta_brain.py) |

## Departments, managers and employees

```mermaid
flowchart TD
    c_departments["Departments (bounded)"]
    c_managers["Manager relationships (partial)"]
    c_employees["Human / AI employee registry (partial)"]
    c_tasks["Governed task queue / states (partial)"]
    c_handoffs["Internal handoffs (partial)"]
    c_departments -->|"same-department manager constraint"| c_managers
    c_managers -->|"optional manager_id relationship"| c_employees
    c_employees -->|"tenant-scoped assignee relationship"| c_tasks
    c_tasks -->|"reviewed cross-department handoff"| c_handoffs
```

| Relationship | Meaning | Evidence |
|---|---|---|
| departments → managers | same-department manager constraint | [OrganizationStore.hire](../../apps/backend/ago/organization_store.py) |
| managers → employees | optional manager_id relationship | [OrganizationStore.hire](../../apps/backend/ago/organization_store.py) |
| employees → tasks | tenant-scoped assignee relationship | [TaskStore.propose](../../apps/backend/ago/task_store.py) |
| tasks → handoffs | reviewed cross-department handoff | [HandoffStore.request](../../apps/backend/ago/handoffs.py) |

## OOS, workflow engine and task queue

```mermaid
flowchart TD
    c_oos["Full OOS — future (planned)"]
    c_scheduler["In-process scheduler (partial)"]
    c_workflow["Plan dependency orchestration (partial)"]
    c_tasks["Governed task queue / states (partial)"]
    c_approval["Independent human approval (bounded)"]
    c_execution["Allowlisted execution (partial)"]
    c_oos -.->|"future resource / lifecycle coordination"| c_scheduler
    c_oos -.->|"future durable organizational control"| c_workflow
    c_workflow -->|"check strategic approval"| c_approval
    c_workflow -->|"materialize dependency-linked tasks"| c_tasks
    c_execution -->|"start only approved eligible tasks"| c_tasks
```

| Relationship | Meaning | Evidence |
|---|---|---|
| oos → scheduler | future resource / lifecycle coordination | Proposed; not implemented |
| oos → workflow | future durable organizational control | Proposed; not implemented |
| workflow → approval | check strategic approval | [PlanExecution.activate](../../apps/backend/ago/plan_execution.py) |
| workflow → tasks | materialize dependency-linked tasks | [PlanExecution.materialize](../../apps/backend/ago/plan_execution.py) |
| execution → tasks | start only approved eligible tasks | [AgentRuntime.run](../../apps/backend/ago/agent_runtime.py) |

## Memory, knowledge graph and communication

```mermaid
flowchart TD
    c_memory["Private persistent memory (partial)"]
    c_graph["Evidence-reviewed knowledge graph (partial)"]
    c_handoffs["Internal handoffs (partial)"]
    c_calendar["Internal calendar (partial)"]
    c_audit["Approval / review audit evidence (bounded)"]
    c_communications["External communications — future (planned)"]
    c_graph -->|"review facts with independent evidence"| c_audit
    c_handoffs -->|"record attributable transition history"| c_audit
    c_calendar -->|"record event response history"| c_audit
    c_graph -.->|"future comprehensive synchronization"| c_memory
    c_communications -.->|"future external delivery connectors"| c_handoffs
```

| Relationship | Meaning | Evidence |
|---|---|---|
| graph → audit | review facts with independent evidence | [KnowledgeStore.review](../../apps/backend/ago/knowledge_store.py) |
| handoffs → audit | record attributable transition history | [HandoffStore.history](../../apps/backend/ago/handoffs.py) |
| calendar → audit | record event response history | [CalendarStore.history](../../apps/backend/ago/calendar_store.py) |
| graph → memory | future comprehensive synchronization | Proposed; not implemented |
| communications → handoffs | future external delivery connectors | Proposed; not implemented |

## Execution, QA, audit, simulation and dashboards

```mermaid
flowchart TD
    c_execution["Allowlisted execution (partial)"]
    c_tasks["Governed task queue / states (partial)"]
    c_qa["Independent QA (bounded)"]
    c_audit["Approval / review audit evidence (bounded)"]
    c_twin["Deterministic Digital Twin scenarios (partial)"]
    c_dashboard["Eight-workspace Control Center (partial)"]
    c_analytics["Operational scorecards (partial)"]
    c_execution -->|"capture run and finish task"| c_tasks
    c_qa -->|"independent task verdict"| c_tasks
    c_qa -->|"retain review evidence"| c_audit
    c_dashboard -->|"query pending QA queue"| c_qa
    c_dashboard -->|"query tenant operational scorecard"| c_analytics
    c_dashboard -->|"request hypothetical assessment"| c_twin
```

| Relationship | Meaning | Evidence |
|---|---|---|
| execution → tasks | capture run and finish task | [AgentRuntime._execute](../../apps/backend/ago/agent_runtime.py) |
| qa → tasks | independent task verdict | [QualityStore.review](../../apps/backend/ago/quality_store.py) |
| qa → audit | retain review evidence | [QualityStore.review](../../apps/backend/ago/quality_store.py) |
| dashboard → qa | query pending QA queue | [pending_qa](../../apps/backend/ago/console_api.py) |
| dashboard → analytics | query tenant operational scorecard | [scorecard](../../apps/backend/ago/api_insights.py) |
| dashboard → twin | request hypothetical assessment | [simulate](../../apps/backend/ago/api_insights.py) |

## Infrastructure, stores and security boundaries

```mermaid
flowchart TD
    c_dashboard["Eight-workspace Control Center (partial)"]
    c_api["FastAPI monolith / routes (bounded)"]
    c_security["Signed sessions / RBAC perimeter (partial)"]
    c_postgres["Shared tenant-scoped PostgreSQL (bounded)"]
    c_outbox["Durable outbox / leased worker (partial)"]
    c_provider["Optional model provider (partial)"]
    c_infrastructure["Docker / migration / recovery tooling (partial)"]
    c_dashboard -->|"same-origin authenticated REST"| c_api
    c_api -->|"signed-session tenant checks"| c_security
    c_security -->|"revocation and active-account checks"| c_postgres
    c_outbox -->|"owned lease claim / acknowledgement"| c_postgres
    c_api -->|"opt-in bounded handler enrollment"| c_provider
    c_infrastructure -->|"checksum migration readiness"| c_postgres
```

| Relationship | Meaning | Evidence |
|---|---|---|
| dashboard → api | same-origin authenticated REST | [create_app](../../apps/backend/ago/main.py) |
| api → security | signed-session tenant checks | [authenticated](../../apps/backend/ago/api_m2.py) |
| security → postgres | revocation and active-account checks | [authenticated](../../apps/backend/ago/api_m2.py) |
| outbox → postgres | owned lease claim / acknowledgement | [EventWorker.run_once](../../apps/backend/ago/event_worker.py) |
| api → provider | opt-in bounded handler enrollment | [optional_model_handlers](../../apps/backend/ago/model_handlers.py) |
| infrastructure → postgres | checksum migration readiness | [schema_integrity](../../apps/backend/ago/release_security.py) |
