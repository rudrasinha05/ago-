# Section 1 — Overall System Architecture Acceptance

## Frozen scope and provenance

Exactly seven requirements from the founder's master Section 1 checklist,
read on 2026-10-10. The complete original V1–V3 blueprint is unavailable;
acceptance here is explicitly against those seven supplied requirements.
This does not replace the blueprint or close any other architecture section.

## Seven-gate checklist

- [x] S1-01: Presentation, application, domain, infrastructure and shared layers mapped to actual registered modules.
- [x] S1-02: All organizational contexts have responsibilities/boundaries; every source module has a policy-derived linked inventory entry; future subsystems remain explicitly identified.
- [x] S1-03: Existing Section 14 guard verifies approved dependency direction, cycles, forbidden coupling and protected SQL ownership.
- [ ] S1-04: Existing backend-to-PostgreSQL HTTP lifecycle passes on this change's CI commit.
- [x] S1-05: Synchronous requests, in-process bus, durable outbox/inbox, commands/events, transactions, leases, retries and delivery guarantees documented without overstating runtime wiring.
- [ ] S1-06: Governed goal/plan/approval/run/QA/audit mapping documented; positive strategic and task/agent regression tests pass on this change's CI commit.
- [x] S1-07: Tenant authority, fault boundaries and scaling limits documented; new traceability/perimeter tests pass locally.

## Local verification

- `python scripts/check_system_architecture.py`: passed, zero violations.
- `python -m ruff check apps/backend/ago apps/backend/tests scripts/check_system_architecture.py`: passed.
- Section 1 regression suite: **6 passed** (source match, three drift failures,
  every private API operation under missing database and dummy no-query DB).
- Existing Section 14 targeted suite: **18 passed** in the initial combined run.
- Initial full suite without PostgreSQL: 216 passed, 59 skipped, two failures;
  one was the new test's mistaken assumption that DB outage always returns 401
  (corrected to test both outage and available no-query DB). The other was the
  existing readiness test expecting a configured PostgreSQL. This environment
  has no PostgreSQL server/client or Docker; database-dependent acceptance is
  delegated to the repository's real disposable PostgreSQL CI, not fabricated.
- One dependency deprecation warning is recorded; it is not a test failure.

## CI acceptance

Pending the pushed implementation commit's actual Python matrix, PostgreSQL,
JavaScript, packaged-wheel, Docker, Chromium and backup/restore results.
Until those results are verified, Section 1 is **in progress**, not fully accepted.

## Change boundaries and rollback

Only architecture docs/inventory, developer checker, regression tests, progress
references and CI invocation change. No app modules, schema, database, provider,
production routes or application behavior are changed. Rollback reverts this
batch; original Section 14 checks remain intact. No founder pull or environment
change is needed during implementation.
