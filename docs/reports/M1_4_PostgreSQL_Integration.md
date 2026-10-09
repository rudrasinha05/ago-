# M1.4 PostgreSQL Integration

## Delivered
- PostgreSQL schema/migration: `deploy/sql/001_events_postgres.sql`.
- Psycopg 3 adapter with atomic outbox insertion inside caller transactions.
- Multi-worker claiming using `FOR UPDATE SKIP LOCKED`, expiring leases and owner-checked acknowledgment.
- Retry with bounded exponential delay and dead-letter status.
- Inbox deduplication with transactionally committed same-database handler writes.
- Optional integration tests (require a running, migrated PostgreSQL test database).

## Local verification
From `apps/backend`:
```powershell
python -m pip install -e ".[dev,postgres]"
psql "$env:AGO_TEST_POSTGRES_DSN" -f ../../deploy/sql/001_events_postgres.sql
python -m pytest -q
python -m ruff check ago tests
```

## Important boundaries
- This integration has been committed, but PostgreSQL integration tests have not been executed against a real database in this session.
- An operational worker loop, lease renewal, operational dead-letter replay, contract versioning, metrics and end-to-end deployment are still outstanding.
- The adapter's inbox provides exactly-once database effects only when all effects share its transaction. External side effects require idempotency.
- Each adapter owns one connection; use separate instances/connections for concurrent workers.
- The project remains in-progress, not release-ready.
