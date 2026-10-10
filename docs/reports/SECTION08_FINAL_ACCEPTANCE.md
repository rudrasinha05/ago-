# Section 8 — Message Bus and Communication Contracts Acceptance

All seven supplied checklist gates are CI-accepted against the frozen scope
in `docs/architecture/SECTION_08_MESSAGE_BUS.md`. The conditional broker gate
is satisfied by the approved existing PostgreSQL multi-process queue; a separate
broker is not required for this modular monolith. No Kafka/RabbitMQ deployment
or external exactly-once delivery is claimed.

Accepted implementation: `cf653f5be7c620a1ede63a570ef28a269c4230c1`.
Primary [38062604255](https://github.com/rudrasinha05/ago-/actions/runs/38062604255)
and independent [38062604261](https://github.com/rudrasinha05/ago-/actions/runs/38062604261)
passed; all nine job conclusions and decoded logs were inspected.

| Gate | Evidence |
| --- | --- |
| Five envelope kinds | Version 1 bounded domain contract and strict authenticated publication DTO; authority/credential injection, malformed approval, nonfinite and oversized payload rejection |
| Durable inbox/outbox | Additive migration 020; atomic publication/audit and consumer inbox/effect/receipt/ack transactions; failed handler rolls back inbox and effects |
| Idempotency and tenant | Persistent tenant/key uniqueness and canonical digest; conflicting duplicate rejected; real concurrent independent connections publish one ID; read/replay scope derived from signed session |
| Distributed queue if required | Existing PostgreSQL SKIP LOCKED; actual independent connections claim disjoint records, ordered lanes block earlier pending/leased records |
| Retry/dead/replay | Expiring token-fenced leases, crash attempts count, three-attempt ceiling, bounded backoff; stale token rejected, poison dead-lettered, authorized human replay retains identity/total attempts and increments replay history |
| Governed approval coordination | Only own existing same-tenant pending request can be referenced; approval decision fields rejected; no approval/execution handler is installed |
| Observability | Tenant-authorized backlog/status/oldest/attempt/order metadata, safe poison error categories and append-only receipts/audits; inspection omits message bodies |

357 Python tests passed each on 3.11, 3.14 and independent 3.12, without skips.
The 14 new tests include actual PostgreSQL HTTP/transaction/concurrency journeys.
All prior 14 console JavaScript, eight SDK, six Chromium, 30 Next.js/browser/axe
and five actual Next.js/PostgreSQL journeys, three builds/exports, packaged wheel,
nonroot read-only image, actual database backup/restore and 18 real model/Redis/
private-object recovery tests passed. Architecture: 101 modules, 267 internal
imports, zero violations; 40 database component ports.

The operator drains event/notification receipts only. Command/query/approval
messages require trusted application handlers and otherwise become observable
dead letters. Terminal dead messages release a lane; explicit replay can revisit
an earlier identity and is not a claim of globally total order. External side
effects need their own idempotency protocol. Earlier unversioned workers cannot
claim/ack/replay the versioned lane. Rollback pauses versioned workers and reverts
the image while retaining additive schema/data; no destructive reverse migration.
