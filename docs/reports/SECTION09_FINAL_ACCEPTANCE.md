# Section 9 — Memory Architecture Acceptance

All seven supplied checklist gates are CI-accepted against
`docs/architecture/SECTION_09_MEMORY_ARCHITECTURE.md`.
Accepted implementation: `fc2ffb78b2ea6e1442ecc928bc4f15bea247938b`.
Primary [38063636010](https://github.com/rudrasinha05/ago-/actions/runs/38063636010)
and independent [38063636007](https://github.com/rudrasinha05/ago-/actions/runs/38063636007)
passed; all nine job conclusions and decoded logs were inspected.

| Gate | Accepted evidence |
| --- | --- |
| Four memory scopes | Employee owner privacy, live department membership, explicit goal-backed project enrollment/revocation and same-tenant company sharing; no founder private-memory bypass |
| Episodic and working context | Typed experience records; working retention at most 24 hours, episodic at most 365 days; expired records denied immediately before cleanup |
| Controlled authorization | Live read/write/manage grants; server-derived actor; same-tenant composite references; strict HTTP inputs; unauthenticated, spoofed owner, cross-tenant and revoked grant denials |
| Vector semantic memory | Actual Section 7 offline 384-dimensional CPU ONNX model, normalized persisted model/revision vectors, authorized scope/expiry before bounded cosine ranking; real paraphrase relevance and private-result exclusion |
| Consolidation/summary/forget | Explicit 2–20 distinct original sources and same scope; verbatim extractive summary with source IDs/revisions and bounded minimum expiry; corrections scrub stale vectors/derived summaries; forgetting physically scrubs content/ref/evidence/vector |
| Evidence and graph links | Same-tenant independently verified knowledge-node reference; no private content publication or implicit fact approval; metadata-only append-only security audit with actor/IDs/revision/digest |
| Retention/privacy/correction | Owner-only optimistic revision correction and forgetting; no privilege widening; idempotent bounded expiry cleanup; project revocation applied live; summary cannot outlive original sources |

371 Python tests passed each on primary 3.11/3.14 and independent 3.12, without
skips. The dedicated real model/Redis/PostgreSQL gate passed 31 tests, including
actual semantic memory retrieval, privacy, corrections and forgetting. Existing
14 JavaScript, eight SDK, six console Chromium, 30 cross-browser/device/axe and
five actual Next.js/PostgreSQL journeys passed, with three Next.js builds/exports,
wheel, nonroot read-only image, populated model/object recovery and real DB restore.
Architecture: 103 modules, 273 imports, zero violations; 41 typed repository ports.

An integration run caught PermissionError being classified as OSError/storage
outage; permission translation now precedes storage handling with an explicit
403-versus-503 regression test. An existing browser test asserted logout request
capture before asynchronous revocation was observed; it now awaits that evidence
without weakening the assertion. Both fixes passed the accepted full CI above.

Memory remains unverified experience; summaries are exact excerpts, not generated
facts. Project means an AGO goal workspace with explicit membership. Legacy
controlled memory API remains compatible; new scoped/vector/lifecycle operations
use `/v1/knowledge/memory`. The 2,000-record tenant bound and exact ranking do not
claim an unbounded ANN service. Forgotten records retain only redacted tombstones
and minimal audit/source IDs; offline backup deletion and retention governance
remain operational responsibilities documented under Section 10.
