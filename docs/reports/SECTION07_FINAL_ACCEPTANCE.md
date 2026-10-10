# Section 7 — Database Architecture Acceptance

All eight supplied Section 7 checklist gates are **CI-accepted** against the
frozen scope in `docs/architecture/SECTION_07_DATABASE_ARCHITECTURE.md`.
Full original blueprint fidelity remains unverified. No production deployment,
new production database/service or operational security certification is claimed.

Accepted implementation: `82a5d229100181c9d488234bf931185fed2c0950`.
Primary CI [38054373301](https://github.com/rudrasinha05/ago-/actions/runs/38054373301)
and independent backend CI
[38054373266](https://github.com/rudrasinha05/ago-/actions/runs/38054373266)
passed. All nine job conclusions and decoded acceptance logs were inspected.
The final closing documentation commit's CI is also verified before delivery.

| Supplied requirement | Accepted implementation and evidence |
| --- | --- |
| Tenant-scoped durable PostgreSQL | Existing authority preserved; composite tenant foreign keys on new vector/object metadata; signed-session same-tenant API and actual second-tenant negative tests |
| Checksum-verified ordered migrations | Additive migration 019; previous 18 files unchanged; fresh and repeated application, source schema checks and actual restored schema verification |
| Redis only for justified cache/queue use | Optional graph-result cache on a configured existing endpoint; actual disposable Redis integration; tenant/source-version/request keys, 60-second TTL and key-bound HMAC; stale version, tampering, absent configuration and outage fall back safely |
| Knowledge graph store such as Neo4j | Existing PostgreSQL reviewed graph extended with indexed incidence traversal, directions, cycle termination, deterministic results and explicit depth/node/work bounds; no separately provisioned Neo4j claim |
| Vector store/semantic embedding index | Actual CPU ONNX BGE-small 384-dimensional embeddings; offline manifest-verified loading, fingerprinted model/source versions, durable tenant/model partition and bounded exact cosine retrieval with source references; real semantic relevance and corrupt-model rejection |
| Documents/artifacts object storage | Authenticated opaque-ID uploads/lists/downloads; private Linux volume, no-follow filesystem operations, exclusive atomic installation, byte/hash checks, quotas and attachment/no-cache perimeter; no partial bytes after DB failure |
| Retention, indexing and recovery policies | Explicit 90-day default / 1–365-day retention, immediate overdue-read exclusion, repeatable tombstone cleanup, idempotent index rebuild and superseded-index removal; private manifests and coordinated offline recovery; immutable knowledge/audit retained |
| Isolated PostgreSQL backup/restore drill | Existing actual dump/checksum/restore gate plus populated Section 7 drill: restored graph, real semantic vectors, object metadata and exact recovered bytes; mismatched metadata manifest rejected |

## Verified regression evidence

- Python 3.11/3.14 primary matrix and independent 3.12: **343 passed each**,
  no skips; one existing Starlette TestClient deprecation warning.
- Dedicated real-model/PostgreSQL/Redis/private-storage gate: **18 passed**,
  including offline CPU model loading with model-network functions forbidden.
  BGE model fingerprint verified in CI:
  `7dc80955164e44310c88afa16ee4bddf883b6fe0fe44f2a442a3f87600d69761`.
- Populated recovery output confirmed `database_restored`, `graph_recovered`,
  `actual_semantic_index_recovered`, `mismatched_manifest_rejected`, and one
  exact recovered private object. Database migration digests were verified.
- Console JavaScript: **14 passed**; shared SDK: **eight passed**.
- Existing real Chromium console: **six passed**.
- Next.js Chromium/Firefox/WebKit desktop/phone/tablet and axe: **30 passed**;
  actual Next.js/signed-session/PostgreSQL journeys: **five passed**.
- All three optimized Next.js exports and actual served homepages, packaged
  wheel and nonroot read-only Docker HTTP smoke passed. Image includes storage
  adapters but startup requires neither Redis nor model downloading.
- All Section 1–6/14 source guards, Mermaid, monorepo, migration and Ruff
  gates passed: **98 registered modules, 260 imports, zero violations/cycles**;
  **39 typed component ports** with reviewed SQL-access ownership.

Local verification passed source guards/Ruff, 14 console JS/eight SDK,
41 targeted unit/backend/context checks and the actual offline-model semantic
test. Full local Python: 276 passed, 66 PostgreSQL-dependent skips and the
established readiness assertion failure because this host has no PostgreSQL
server/DSN. All corresponding database gates passed against real PostgreSQL in
CI. The initial CI assertions were corrected to acknowledge version invalidation
on rejected-node review and the existing stronger `no-store, private` download
header; authority and cache-integrity requirements were preserved.

## Bounded operational contract

This is the existing modular monolith and PostgreSQL database. Redis is an
optional cache adapter, not an authorization or approval authority. The vector
store is a tenant/model-indexed PostgreSQL array partition with a bounded CPU
cosine scan, not ANN or deployed pgvector. The English BGE model has a bounded
token window; multilingual/chunked document ingestion and broader relevance
certification are not implied. Uploaded bytes remain untrusted source evidence,
and facts still require the existing independent human review.

Operators configure a private Linux object volume and explicitly prepare the
offline model. Native Windows object storage fails unavailable; the existing
Linux service image hosts that adapter. Documents use tenant-wide knowledge
permissions. Retention/rebuild are deliberate maintenance commands, not newly
deployed scheduler services. Caller rollback/process crash can leave inaccessible
orphan bytes; reconcile offline before deletion. Backups require stopped writers,
per-tenant object manifests, the PostgreSQL snapshot and the prepared model.
Only an isolated, verified restore is accepted; production cutover remains an
independently authorized operator operation.

Rollback is an application image revert while retaining additive migration 019,
new metadata and objects. No automated data deletion, database reset or reverse
migration. Section 8 remains independently pending under the one-section rule.
