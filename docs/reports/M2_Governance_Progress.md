# M2 governance progress — implementation checkpoint

The founder reported 83 pytest tests passed after the first M2 approval domain slice.

This checkpoint adds:
- A fail-closed constitution classifier: unknown actions require approval.
- PostgreSQL migration 004 for tenant-scoped approval requests and append-oriented audit records.
- A transactional approval repository with row locking and terminal-state enforcement.
- A mandatory caller-supplied reviewer authorization gate (default denied).
- Unit tests for conservative policy and missing authorization.

## Explicit limitations
- The repository is **not** exposed as a public API and is not yet wired to actual tool execution.
- The `authorized` argument is trusted only when supplied by server-side authorization code; do not accept it from HTTP request bodies.
- Audit records are not database-enforced immutable; privileged DB users can still alter them.
- No production-ready reviewer RBAC or session authentication integration yet.
- Migrations and new tests must be run on the founder's local PostgreSQL installation.
- Live readiness HTTP response is still not recorded.

## Local acceptance
From `apps/backend`, with `AGO_POSTGRES_DSN` and `AGO_TEST_POSTGRES_DSN` set:
```powershell
git pull --ff-only origin develop
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```
