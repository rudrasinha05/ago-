# M1.4 Event Worker Checkpoint

Added an async polling worker with PostgreSQL outbox claim/ack/failure adapter protocol, bounded batches, cancellation propagation, graceful stop and structured batch report.

**Semantics:** at-least-once delivery, not exactly-once. A crash after a handler succeeds but before acknowledgment causes redelivery. Handlers must be idempotent. Leases can expire while a long-running handler is active; lease renewal and delivery timeouts are not implemented yet. Store methods run on a thread; each store instance must only be used by one worker at a time.

**Outstanding:** live PostgreSQL integration verification, schema migration runner, production lifecycle wiring, lease renewal, event schema versioning, metrics, dead-letter replay, hardening. Do not mark M1.4 production-ready.
