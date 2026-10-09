# AGO M3–M5: consolidated delivery scope (BDR)

Preserve the modular-monolith-first architecture (Blueprint Sections 0–35), M1/M2 foundations, and sole `develop` branch. The goal is **three complete, testable backend milestones**; this is not a claim that all Sections 0–35 or a commercial autonomous enterprise are done.

## M3 — Company Brain & strategic planning
- Tenant-scoped organizational goals with parent hierarchy and lifecycle.
- Version-safe action plans and DAG steps assigned to organizational employees.
- Independent human approval of plan activation via existing approval subsystem.
- Materialize steps into governed tasks; task approval and prerequisite QA stay mandatory.
- Session/RBAC-protected APIs and PostgreSQL integration tests.

## M4 — Governed agent operations
- Persisted AI agent job runs tied to approved tasks, employee identity and tenant.
- Operator-authorized, allowlisted **application-defined** tool/provider handlers.
- Fail-closed runtime: no automatic tool discovery, no shell, spending, publishing or access changes.
- Captured outputs, failure signals, idempotent run claim, explicit quality gates.
- Tests for permissions, crashes, replay and isolation.

## M5 — Economics, observability and simulations
- Per-tenant credit budget with transactionally bounded usage and idempotency.
- Tenant scorecards (goals/plans/tasks/reviews/agent runs/credit balance).
- Deterministic what-if simulation, risk flags and policy-change *proposals* only.
- Approved proposals never silently change code, policies or organization.
- Secure API, audit and integration tests.

## Acceptance
Use existing GitHub Actions with isolated PostgreSQL for migrations, Ruff and full pytest suite, including cross-tenant denial, unauthorized access, replay, workflow integrity and budget concurrency/replay tests. Record exact CI run, test count and SHA. No local pull before all three have passing gates.

## Limits
M3–M5 represent approved functional backend vertical slices, **not** deployed AGI, self-improving agents or a production release. Provider credentials, external tool side effects, hosted frontend, load benchmarks and disaster recovery remain separate production/future integration gates.
