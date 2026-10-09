# M2 — Organizational governance foundation

M1 evidence supplied by the founder: PostgreSQL migrations applied, 75 pytest tests passed, one nonblocking Starlette warning. Live HTTP readiness remains to be verified separately.

## M2 scope (implementation order)

1. Corporate constitution and action classification (which actions require human approval).
2. Durable, tenant-scoped approval requests and decisions, with authorization and audit trail.
3. Organizational structure, departments, positions and AI employee identity.
4. Governed task/workflow orchestration and execution adapters.
5. Independent QA/audit gates and organizational memory interfaces.
6. M2 integration, threat-model review and acceptance tests.

The sequence is subordinate to the existing Sections 0–35 architecture and BDR; no architectural reset.

## First implementation slice

`ago.approvals` provides an immutable, in-memory domain decision model with default-deny execution checks, tenant and action scoping, independent reviewers, and final decisions. Tests cover these invariants.

**Not yet complete:** persistence, reviewer role authorization, immutable audit history, concurrent decision handling, API wiring, and enforcement by actual execution adapters. This is **not** a live approval system or production authorization boundary. Never use the pure domain model alone to authorize real-world actions.
