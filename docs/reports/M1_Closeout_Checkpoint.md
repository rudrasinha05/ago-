# M1 — Foundation closeout checkpoint

## Implementation inventory
- M1.1 Configuration and environment settings: implemented baseline.
- M1.2 Request correlation and structured logging baseline: implemented.
- M1.3 Dependency injection container: implemented and unit-tested previously.
- M1.4 In-memory events, SQLite/PostgreSQL outbox/inbox, migrations, worker and dead-letter operations: implemented baseline.
- M1.5 Tenant identity persistence, password hashing, signed token primitives and opt-in login router: implemented baseline.
- M1.6 Tenant-aware role authorization, persistent grants, revocation primitives and API guards: implemented baseline.
- M1.7 Trusted plugin registry and lifecycle: implemented baseline.
- M1.8 In-process interval scheduler: implemented baseline.
- M1.9 Metrics, readiness check registry and feature flags: implemented baseline.

## Release decision
**M1 is feature-implementation complete at foundation level, but verification gates remain open.** Do not label production-ready or fully accepted.

## Required local verification
From apps/backend:

```powershell
git switch develop
git pull --ff-only origin develop
python -m pip install -e ".[dev,postgres]"
python -m ruff check ago tests
python -m pytest -q
python -m uvicorn ago.main:app --reload
```

Check /health/live and /health/ready. The current /health/ready API response is a basic stub and must not be interpreted as verified dependency readiness.

## PostgreSQL gate
Set AGO_TEST_POSTGRES_DSN to a dedicated disposable test database, apply migrations using `python -m ago.event_runtime migrate --dsn <TEST_DSN>`, then run integration tests. Never run destructive test operations against production.

## Open engineering risks
- Latest unit/lint suite and live PostgreSQL integration have not been executed in this assistant session.
- API login is opt-in and is not production-hardened; in-process rate limiting is not distributed.
- Revocation primitives are opt-in and not wired to all endpoints.
- No MFA, trusted OIDC, token rotation or complete audit coverage.
- Worker lacks automatic lease renewal for long-running handlers; scheduler is not durable/distributed.
- Plugins are trusted Python modules, not sandboxed; metrics and feature flags are in-memory.
- Readiness endpoint is not yet backed by actual dependency probes.

**Checkpoint outcome:** ready for local pull and verification; not yet eligible for unconditional M1 acceptance.
