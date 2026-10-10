# Section 8 — Frozen Message Bus and Communication Contracts

Baseline `30ee90f`; status in progress. Scope is the seven supplied master
checklist requirements; the full original blueprint remains unavailable.
The founder authorized sequential completion of Sections 8–10 in one batch;
the usual stop-before-next-section rule does not require another confirmation
within this authorized batch. Each section retains its independent gates.

| Gate | Acceptance and negative evidence |
| --- | --- |
| Command/event/query/notification/approval envelopes | Versioned, bounded immutable identities, actor/tenant/correlation/idempotency and ordering metadata; reject injected authority, malformed schemas, conflicting duplicate keys and cross-tenant references |
| Durable inbox/outbox | Extend existing PostgreSQL outbox; transactional publication and inbox/effect/ack commits; rollback and duplicate delivery tests |
| Idempotency/tenant validation | Same-tenant persistent idempotency key and content digest; consumer inbox exactly-once only for effects sharing its database transaction; no external exactly-once claim |
| Approved distributed broker if required | Not required for this bounded modular monolith. Existing PostgreSQL SKIP LOCKED supports multiple processes; real independent-connection lease/ordering tests. No new production service or pretend Kafka/RabbitMQ deployment |
| Retry/dead-letter/replay | Expiring token-fenced leases, bounded delivery attempts including crashes, backoff, explicit human-authorized audited replay preserving ID/total attempt history; stale token/lease and poison tests |
| Approval coordination | Approval messages reference an actual same-tenant pending request; cannot create approval decisions or authorize execution; existing independent governance workflow remains mandatory |
| Observability | Tenant-authorized status/backlog/oldest/poison/ordering metadata with safe error categories and receipt/audit records; another tenant cannot observe/replay queues |

Artifacts: additive migration 020, framework-free envelope contract,
caller-owned message repository/typed port, existing `/v1` knowledge router
transport adapters, explicit operator drain entrypoint, actual PostgreSQL and
negative unit tests, architecture/SQL/port manifests and acceptance report.
Old unversioned event records and worker interfaces remain compatible and
separate from the new versioned message lane. No approval handler is introduced.
Notification/event receipt handling is safe and non-business-mutating; commands
and queries require explicit trusted registered handlers and otherwise dead-letter.

Ordering is FIFO per tenant/key while earlier messages are pending/leased;
terminal delivered/dead messages release the lane. Delivery is at least once;
external effects require their own idempotency contract. New schema is additive;
rollback reverts the image, retains queued messages and pauses versioned workers.
No drop/reset/reverse migration. Actual CI, including prior storage/browser/image
and recovery jobs, must pass before any Section 8 checkbox is closed.
