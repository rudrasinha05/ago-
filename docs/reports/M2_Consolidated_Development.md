# AGO M2 consolidated development checkpoint

This checkpoint covers six M2 workstreams on the existing modular-monolith develop branch:

1. Constitution: conservative high-risk classification (unknown actions require approval).
2. Approvals: immutable domain decisions, PostgreSQL migration 004, transactional repository and audit event inserts.
3. Organization: departments, humans/AI employees, same-department reporting structure domain model.
4. Workflow: explicit task state machine, approval references and fail-closed transitions.
5. Independent QA and memory: reviewer separation, evidence requirements, tenant/private read boundaries.
6. Tests and acceptance: added unit tests; founder must run migration, lint and full suite once after pulling.

## Security / readiness limits
These are **foundations**, not complete operational enterprise workflows. Organization, task and memory models are in-memory and not yet persisted. The workflow authorize method only matches an approval reference; callers must check durable approval status and RBAC using trusted server-side identity before calling it. No live external execution adapters are wired. Audit records can be modified by privileged database accounts. No end-to-end M2 acceptance or production readiness claim.

## One-shot verification (PowerShell, apps/backend)
Ensure AGO_POSTGRES_DSN and AGO_TEST_POSTGRES_DSN are set in the same session.
```powershell
git pull --ff-only origin develop
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```
