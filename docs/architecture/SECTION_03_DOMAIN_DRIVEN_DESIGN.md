# Section 3 — Domain-Driven Design

## Source and frozen acceptance

The founder's current seven Section 3 checklist requirements are the bounded
scope. Original full-blueprint parity remains unavailable. This is a
modular-monolith context contract; it preserves working modules, schema and
approved dependencies. Identity is a subdomain of the governance context;
transport and entrypoints are technical contexts rather than business aggregates.

All nine contexts are specified in `section03_domain_contracts.json` with
purpose, aggregates, value objects, repositories, application/domain services,
invariants, published language and consistency. Every source module has an
explicit context. Existing records implemented as dictionaries are described
as records, not falsely presented as new rich entity classes.

| Gate | Evidence |
|---|---|
| Identify all bounded contexts | Nine-context contract; identity/security under governance, plus strategy/workforce/knowledge/operations/economics/platform/transport/composition |
| Aggregates/entities/value objects | Explicit per-context catalog and implemented source symbols in Sections 1–2 |
| Repositories/services/invariants | Per-context contract and tested existing domain/store boundaries |
| Tenant organization/goals/tasks | Existing PostgreSQL regression plus Section 2 combined path |
| Events/context contracts/published language | Envelope and interaction rules below; contract catalog |
| Context isolation architecture tests | Every module mapped; exact import guard and reviewed table-access roster; negative imports/reads/owner drift tests |
| Eventual consistency and transactions | Transaction/recovery rules below and existing leased-worker/idempotence tests |

## Aggregate authority and ownership

Governance owns identity, approval decisions, council authorization, independent
QA and audit. Strategy owns goals, plans and immutable policy/advice versions.
Workforce owns organizational records, assignees, task state and agent runs.
Knowledge owns private memory semantics and evidence-reviewed nodes/edges.
Operations owns handoffs, calendar and reviewed tools/triggers. Economics owns
virtual quota and usage, while platform supplies events, leases and runtime
primitives without independent business authority.

Ownership is logical. `MemoryStore` currently lives in `organization_store` and
transport sometimes uses repositories directly: these reviewed bridges are
explicit, not silently treated as perfect clean-architecture isolation. Module
imports remain governed by Section 14. The Section 3 SQL-access manifest records
all statically visible `ago_*` tables per module; new or removed accesses require
review and a contract update. A SQL baseline is not authorization to read all
rows. Tenant/privacy/RBAC predicates and PostgreSQL constraints remain mandatory.

A department/employee manager reference cannot cross the department; a plan
cannot borrow another tenant's goal/assignee; prerequisite QA blocks dependent
tasks; strategic approval never replaces task approval. A model, event or
cross-context call cannot create an authorization grant. These invariants are
exercised by existing PostgreSQL and HTTP tests, not merely asserted in prose.

## Context contracts and published language

Synchronous contracts use server-derived `Principal(subject, tenant_id, roles)`,
validated identifiers, specific repository operations and versioned `/v1` DTOs.
Inputs carry facts/intent, never an authoritative client permission flag. The
OpenAPI definitions are the current transport language; future extraction must
preserve tenant scope, independent human gates, idempotence, compatibility and
error semantics. No direct connection object may become a public network API.

Commands request work, queries retrieve permitted records, and events describe
facts. Existing `Event` contains name, object payload, ID, UTC occurrence and
optional correlation. `_version` identifies payload contract version when
validated through `EventRegistry`; missing version means v1. Private consumer
contracts additionally require tenant/provenance in the relevant payload and
consumer checks. The general envelope does not universally add a tenant field;
its absence is not silently upgraded into a tenant-aware enterprise broker.
Unknown versions/payloads fail enrolled registry validation. New business event
names are not invented or automatically emitted by this documentation.

Approval IDs, plan/task states, QA verdict/evidence, reviewable knowledge facts,
internal calendar/handoff states and virtual credit records are the published
organizational languages. Event contracts complement these; they do not
replace authoritative persisted state or make all contexts eventually consistent.

## Transaction and eventual-consistency rules

An aggregate change and its owned audit/ledger updates commit in one explicit
PostgreSQL transaction. Cross-context references are checked under the same
tenant and appropriate constraints. Existing plan materialization may coordinate
workforce writes in a shared transaction through approved repositories. This is
a reviewed monolith integration, not a distributed saga.

Strategic activation and each task's later approval/run/QA are distinct bounded
operations. Agent claim commits before handler execution; result/evidence/task
completion commit afterward. Failure or crash cannot be treated as successful
execution or auto-replayed consequential work. An independent reviewer must
interpret captured evidence before a downstream dependent task becomes eligible.

Durable notification requires producer state and outbox write in the same
transaction. Worker leases and idempotent inbox consumption provide at-least-once
delivery; consumers may lag or receive duplicates. Stale leases recover delivery,
not permission. Cross-context read models/scorecards are timestamped snapshots,
not globally serializable company state. External side effects cannot commit
atomically with PostgreSQL: explicit consent, idempotence/reconciliation and
rollback/compensation contracts precede future integration.

## Enforcement, limits and rollback

`python scripts/check_domain_contexts.py` verifies every module against its
registered owner, every context's full contract, all reviewed table references
and Section 14 import/layer/cycle rules. Tests inject unauthorized SQL reads,
imports, owner reassignment and incomplete context contracts. This static
boundary audit is not a SQL parser or universal proof of runtime privacy;
real tenant/auth/approval/QA regressions supply that separate evidence.

The manifest is updated only after reviewed context changes; it grants no new
DB roles. No runtime behavior, schema or business service changes in this
section. Rollback reverts its contract/checker/tests/docs and CI step; previous
architecture guards and tenant data remain. Acceptance is recorded in
`docs/reports/SECTION03_FINAL_ACCEPTANCE.md` before starting Section 4.
