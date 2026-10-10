# Section 2 — High-Level Component Diagram

## Provenance and full bounded scope

Source: the founder's current `AGO_Architecture_Sections_01_34_Master_Checklist.md`,
Section 2, read 2026-10-10. Baseline `4ee6c03`. The original complete blueprint
is still unavailable; this delivers all seven supplied Section 2 requirements
without inventing or replacing that original document. Sections 1 and 14 remain
unchanged. No missing subsystem is implemented just to populate a diagram.

| Gate | Full acceptance |
|---|---|
| S2-01 | Company Brain, Meta Brain and Executive Council view |
| S2-02 | Department, manager and employee view |
| S2-03 | OOS, workflow orchestration and task queue view |
| S2-04 | Memory, graph and communication view |
| S2-05 | Execution, QA, audit, simulation and dashboard view |
| S2-06 | Infrastructure, data-store and security-boundary view |
| S2-07 | Actual integrated brain, approval, employee execution and independent QA path against PostgreSQL |

## Diagram package and meaning

[Six source-linked component views](SECTION_02_COMPONENT_VIEWS.md) provide the
complete catalog and evidence for every current relationship. Each view is
scoped to one organizational concern, uses top-down layout, and distinguishes
existing narrow capability, partial foundation and absent future scope.
`section02_components.json` records nodes, capability statuses, edges and exact
source symbols. The developer generator validates those symbols and regenerates
Mermaid views deterministically. The existing Section 14 policy remains the
source of import permissions; these organizational views grant no permissions.

A solid arrow means the labelled existing relationship: it may be an operation,
a query, a stored reference, an organizational constraint or retained evidence.
It does not imply a bidirectional runtime API, distributed service, control
loop or an automatic invocation. A dotted arrow means proposed future scope.
The accompanying relationship tables identify the exact evidence and meaning.

## Current implementation and target boundary

Company Brain creates goal/plan records and approved dependent tasks. Meta Brain
uses evidence and DNA thresholds to produce reviewable advice. Council requires
quorum and a separate human approval. These three do not form an autonomous
chain in which council advice can bypass task approval.

Departments and employees are tenant-scoped records. A manager is an optional
relationship constrained to the department, not an independently running
manager service. Task assignment and handoff records do not grant execution
permissions or transfer approval across tenants.

The OOS target is shown as future: existing in-process scheduling and dependency
materialization are foundations. They are not a full durable organizational
resource allocator. Tasks live in PostgreSQL with governed states; this is not
an installed RabbitMQ/Redis broker. Starting a task, completing its handler and
passing independent QA are separate transitions.

Private memory and evidence-reviewed knowledge nodes exist; comprehensive
memory/graph synchronization is shown as proposed. Handoffs and calendar history
supply internal collaboration, not email/chat/meeting connectors. External
communication remains future scope. Node visibility and tenant permissions
continue to be enforced by their repositories.

Execution stores run results and evidence. QA accepts or rejects independently;
approval/review audit is attributable durable evidence, not a separate certified
security audit service. The Control Center reads permitted queues, operational
scorecards and deterministic hypothetical simulations. The Digital Twin does
not autonomously apply scenarios to production or simulate an entire workforce.

## Trust and physical deployment boundaries

The first-party console is served from the same FastAPI origin. Signed session
verification and database-backed identity/revocation/RBAC checks mediate private
operations. The API and organizational components share one process and database;
component separation is logical, not a claim of process/network isolation.

PostgreSQL is the currently deployed transactional store for tenant-scoped
records, memory, graph facts, audit and outbox. Leased dispatch runs via an
operator-invoked worker; it is not automatically started by app assembly. Docker,
ordered/checksummed migrations, readiness and backup/restore are reviewed
infrastructure tools. Redis, Neo4j, vector/object stores, Kubernetes, multi-region
operations and production observability remain independent section work.

The optional model boundary requires explicit operator configuration and bounded
handler enrollment. A model response has no power to alter permissions, approve
work or execute arbitrary tools. External use stays off by default; no provider
calls or new infrastructure are introduced by this diagram deliverable.

## Cross-component acceptance and regression

`test_section02_company_path_postgres.py` drives a single real workflow through
Company Brain goal/plan creation, independent strategic approval, task
materialization, separate action approval, an allowlisted employee run,
independent QA and durable evidence/audit queries. Negative assertions prove
that strategic consent does not authorize the task, self-QA is denied and the
run cannot replay. Disposable fixtures roll back; no production tenant is used.

`test_section02_component_diagrams.py` verifies all six views, required nodes,
source symbols, deterministic output, absent-target status, proposed/current
edge distinction, endpoint integrity and diagram drift. Missing symbols or
unsupported current edges fail; generation cannot silently convert future
scope into implemented software.

The CI matrix checks diagram/source consistency before migrations and executes
the integrated PostgreSQL regression with the complete suite. Mermaid syntax
is also checked with the pinned developer-only parser; its packages are not
application runtime dependencies. Existing JS, Chromium, Docker and recovery
gates continue to protect prior functionality.

## Maintenance and rollback

After a reviewed component change, edit the catalog, verify source evidence,
run `python scripts/check_component_diagrams.py --write`, review the changed
views and run tests. Diagram regeneration does not authorize architecture or
scope changes. Missing evidence must be fixed or its capability marked future;
do not relabel an absent subsystem as working.

Rollback reverts this section's catalog, diagrams, developer checks, tests and
CI invocation. Application code, schema, providers, Sections 1/14 and existing
runtime behavior do not change. Final evidence belongs in
`docs/reports/SECTION02_FINAL_ACCEPTANCE.md` and the master checklist. Acceptance
of this diagram section does not close the subsystem engineering sections.
