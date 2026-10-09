# M1.4 Consolidated Hardening Batch

Implemented on develop:
1. Versioned event contract registry with per-domain payload validators.
2. Ordered PostgreSQL migration runner with checksums and advisory transaction lock.
3. Lease renewal and explicit operator-controlled dead-letter replay.
4. Additional unit tests and optional PostgreSQL integration coverage.

## Boundaries and next validation
- Live PostgreSQL integration tests still require a real migrated database.
- Event contracts are opt-in; outbox enqueue does not yet enforce registry validation.
- Lease renewal API exists, but the polling worker does not automatically renew long-running handlers' leases.
- Migrations require a dedicated migration connection with autocommit enabled; use the SQL directory `deploy/sql`.
- Dead-letter replay is a privileged administrative operation; no authenticated API is exposed.
- Existing worker is at-least-once and handlers must be idempotent.
- No claims of release readiness or completed M1.4 audit.

Consolidated local checks (when requested):
```powershell
git pull origin develop
python -m pip install -e ".[dev,postgres]"
python -m ruff check ago tests
python -m pytest -q
```
