# M1.4 Event Bus — implementation checkpoint

Status: **In progress**. The current implementation is an in-process event bus, not a distributed/durable enterprise event platform.

Implemented:
- Immutable event envelopes with UUID, timestamp, payload, optional correlation ID.
- Exact-name and wildcard subscriptions; unsubscribe callback.
- Async/sync handlers, sequential deterministic dispatch, handler isolation.
- Bounded immediate retry and structured dispatch failure result.
- Unit tests covering successful dispatch, unsubscribe, wildcard, async handlers, retries, failure isolation and cancellation.

Not implemented / not claimed:
- Transactional outbox/inbox, persistent storage, deduplication across restarts.
- Dead-letter queue, delayed retries/backoff, durable consumer offsets.
- Event schemas/versioning, access policy, distributed tracing, replay, metrics.
- Production readiness, end-to-end integration and load tests.

The foundation roadmap remains unchanged. The earlier local Codex source still needs migration/reconciliation.
