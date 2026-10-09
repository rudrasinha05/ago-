# M1.4 — Durable Events Checkpoint

Implemented a local SQLite-backed transactional outbox and consumer inbox:
- Event enqueue inside a caller-provided SQLite transaction.
- Pending event lookup, delivered status, retry delay and dead status.
- Per-consumer deduplication and atomic handler side-effects when those effects use the same SQLite connection.
- Persistence/restart, rollback, deduplication, and failure tests.

**Scope boundary:** This is a single-node persistence adapter. It is **not** a distributed, production-safe event transport. It lacks atomic multi-worker leasing, durable scheduling, operational dead-letter replay, PostgreSQL adapter, metrics, event schemas/versioning, and a managed delivery worker. The in-memory event bus remains separate; the adapter does not automatically dispatch outbox records. The inbox's exactly-once guarantee applies only to writes within the same SQLite transaction. External side effects are not exactly-once.

Status: M1.4 in progress, not release ready.
