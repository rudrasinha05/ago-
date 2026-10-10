# Section 7 — Database Architecture: Frozen Acceptance Scope

Status: **All eight bounded gates CI-accepted**, implementation `82a5d22`,
primary run `38054373301`, independent run `38054373266`.
Frozen baseline: `9328086` on `develop`. Evidence is recorded in
`docs/reports/SECTION07_FINAL_ACCEPTANCE.md`; the frozen requirements below
remain separate from their actual test results.

## Source and bounded scope

The source is Section 7 of the founder's
`AGO_Architecture_Sections_01_34_Master_Checklist.md`, Library version 6,
read on 2026-10-10. Its eight requirements are preserved below. The full
original enterprise blueprint is unavailable; source fidelity beyond these
requirements is not asserted. The standing delivery rule is
`docs/BDR_SECTION_DELIVERY_RULE.md`.

Existing evidence: PostgreSQL tenant constraints and 18 ordered,
checksum-verified migrations; independently reviewed knowledge nodes and
append-only edges in migration 012; signed-session knowledge APIs;
isolated PostgreSQL backup/restore tooling. An incidence query is not yet a
complete traversal store, and an evidence reference is not document storage.
PostgreSQL backup alone cannot recover external document bytes.

## Implementation decisions and dependency boundaries

1. PostgreSQL remains the transactional authority in the existing modular
   monolith. Add ordered migrations; never alter already applied SQL.
2. Extend the existing PostgreSQL knowledge graph rather than provision a
   separate Neo4j service. The checklist says "such as Neo4j"; acceptance
   requires actual tenant-isolated, indexed, bounded traversal, not a
   claim that Neo4j has been deployed.
3. Semantic retrieval must use actual versioned model embeddings. Evaluate
   local CPU ONNX FastEmbed with `BAAI/bge-small-en-v1.5` (384 dimensions)
   before selecting a pinned compatible dependency and model artifact.
   Model preparation is an explicit operator/build operation, never a
   request-triggered download. Persist model identity and source identity
   with the index in PostgreSQL. Exact bounded cosine retrieval is acceptable
   only if its scope and limitations are explicit; it must not be called an
   approximate nearest-neighbor index. A pgvector extension requires a
   separate compatibility/recovery decision before migration adoption.
4. Document objects use a private operator-configured storage directory in
   the existing service's persistent volume, with PostgreSQL metadata.
   Opaque tenant/object identifiers determine paths; submitted filenames
   never determine filesystem paths. No public static object mount.
5. Redis is optional derived traversal caching, never session, permission,
   approval, graph, queue or audit authority. Do not provision a new Redis
   service. An explicitly configured existing Redis endpoint is sufficient
   for this adapter; disposable Redis in CI proves integration. No endpoint
   means PostgreSQL-only operation. Every request checks authorization first;
   PostgreSQL source versions invalidate old cache entries, and corruption
   or outage falls back to authoritative reads.
6. Immutable knowledge and audit history remain immutable. Retention applies
   to owned document bytes and rebuildable derived indexes/cache. Document
   expiry must retain an explicit metadata tombstone and make subsequent
   reads unavailable. This is not enterprise legal erasure or compliance
   certification.

No production provisioning, paid-provider activation, destructive cleanup,
database reset or automatic approval is part of this section. A newly required
database/service would need the separately approved architecture decision
specified by the standing delivery rule.

## Eight acceptance gates

| Original requirement | Required executable evidence | Negative/failure acceptance |
| --- | --- | --- |
| Provision PostgreSQL tenant-scoped durable transactional storage | Existing real-PostgreSQL tenant fixtures plus new storage metadata with tenant-scoped foreign keys and caller-owned transactions | Foreign-tenant reads/references fail; rollback leaves no visible partial metadata |
| Maintain checksum-verified ordered SQL migrations | Existing migration runner plus fresh/repeated application of new ordered SQL; applied-file digests remain unchanged | Modified applied migrations fail; rerun preserves data and object references |
| Introduce Redis only for justified cache/queue use cases | Optional traversal cache, tenant/source-version keys, bounded TTL, disposable real-Redis integration; documented cache-only rationale | Missing configuration, unavailable Redis, invalid payload and stale graph version return authoritative PostgreSQL results; permission revocation remains effective |
| Build the specified knowledge graph store such as Neo4j | Authenticated traversal over existing independently reviewed PostgreSQL nodes/edges, incidence indexes, deterministic ordering, explicit direction/depth/node/work limits | Cycles terminate; pending/rejected or foreign-tenant nodes stay invisible; invalid limits and missing roots fail safely; truncation is explicit |
| Implement vector store/embedding index for semantic search | Versioned actual embeddings, persisted tenant/source/model metadata, authenticated retrieval with evidence references, deterministic ties and documented rebuild command | No model causes a safe unavailable result; malformed/nonfinite/wrong-dimension vectors fail; pending/rejected and foreign-tenant knowledge never appears; real-model semantic relevance is tested |
| Implement object storage for documents and artifacts | Bounded authenticated upload/list/download, opaque names, exact-byte hashes, atomic writes and private metadata/object storage integrated into the knowledge context | Unauthorized/foreign-tenant access fails; path traversal, symlinks, excessive size and corrupt/missing bytes fail safely; write failures do not expose incomplete objects |
| Set explicit data retention, indexing and recovery policies | Documented limits/defaults, explicit operator expiry/rebuild, metadata tombstones, object manifest/hash verification and coordinated database/object recovery instructions | Retention never deletes immutable knowledge/audit; interrupted maintenance is retryable; checksum mismatch and inconsistent recovery metadata are rejected |
| Validate isolated PostgreSQL backup and restore drill | Preserve existing actual PostgreSQL isolated restore gate and extend storage recovery verification to restored graph/index/metadata plus recovered object bytes | Source/target confusion is rejected; missing/corrupt object backups fail verification; no production database is wiped |

These are acceptance requirements, not test results. The first, second and
eighth checklist items have existing evidence but must pass regression with
the final Section 7 implementation. The remaining five stay unchecked in the
master checklist until actual final-commit CI evidence is inspected.

## Concrete implementation and verification artifacts

- Owned persistence and typed repository ports for graph traversal, semantic
  index and document metadata; transport uses the existing signed-session
  dependency and server-derived tenant, with `knowledge:read`/`knowledge:write`
  or an explicitly reviewed permission addition.
- Ordered SQL migration(s), reviewed architecture manifest/SQL-access/port
  contracts, source inventory and component evidence updated together.
- Private object adapter and explicit preparation, retention, rebuild and
  recovery operator commands; provider failures use sanitized errors.
- Positive/negative unit tests and real PostgreSQL HTTP/integration tests;
  dedicated real model/Redis/object-recovery CI where runtime dependencies
  require a supported Python version. Injectable test encoders do not count
  as real-model acceptance.
- Existing Python matrix, source guards, Ruff, JavaScript, browser, wheel,
  nonroot Docker and PostgreSQL recovery jobs remain green. Service startup
  must not require Redis or a network model download.
- `docs/reports/SECTION07_FINAL_ACCEPTANCE.md`, the section ledger and the
  single master checklist updated only after implementation and decoded CI
  evidence, including the closing documentation commit, are verified.

## Migration and rollback contract

New data structures are additive. Deploy SQL before enabling new routes.
Rolling the application image back disables new functionality while retaining
new tables/objects; do not automatically drop storage or reverse migrations.
Recovery restores into an isolated target and verifies database migration
digests, metadata and object hashes before operator cutover. An object restore
is a separate step from PostgreSQL restore and must be tested as such.

Section 8 remains unstarted until every Section 7 gate is accepted or an exact
external operational blocker is recorded under the standing delivery rule.

## Implemented interfaces and operator contract

Implementation artifacts: migration `019_database_architecture.sql`,
`DatabaseStore` and its typed request-scoped port, private byte/offline embedding/
signed Redis adapters, and `python -m ago.storage_ops`. FastEmbed is pinned to
0.7.4 and redis-py to 6.4.0; the existing Linux image includes both adapters.
No model is downloaded during image build, application startup or an HTTP
request. Model preparation copies downloaded weights into a self-contained
directory, rejects runtime symlinks and fingerprints all installed files.
The runtime model identity includes that SHA-256 fingerprint.

| Authenticated knowledge API | Required permission |
| --- | --- |
| `GET /v1/knowledge/nodes/{id}/graph` | `knowledge:read` |
| `POST /v1/knowledge/nodes/{id}/index` | `knowledge:write` |
| `POST /v1/knowledge/search` | `knowledge:read` |
| `POST /v1/knowledge/documents` | `knowledge:write` |
| `GET /v1/knowledge/documents` | `knowledge:read` |
| `GET /v1/knowledge/documents/{id}` | `knowledge:read` |

All tenants are derived from the existing signed session. Uploads use strict
JSON with `filename`, `media_type`, `content_base64` and optional
`retention_days`; downloads are non-cacheable octet-stream attachments with
opaque download filenames. Objects are untrusted evidence bytes: uploading a
PDF does not parse it, verify its content or automatically make it a reviewed
fact. The returned `ago-object:{id}` reference can be supplied as evidence on
the existing independently reviewed knowledge-node flow. Shared object access
is tenant-wide knowledge access; employee-private document ACLs and ingestion
pipelines are separate backlog work, not implied capabilities.

Limits: graph depth 0–4, nodes 1–200, at most 2,000 examined edges with explicit
truncation; vectors 384 dimensions, at most 2,000 per tenant/model; exact cosine
top 1–50 and queries up to 1,000 characters. A PostgreSQL composite primary
index selects the tenant/model vector partition; ranking is a bounded CPU scan,
not ANN. Vectors are normalized, finite and source-digest checked. Model rebuild
is idempotent and removes superseded model vectors only after rebuilding all
currently reviewed sources succeeds. Growth beyond this explicit capacity
requires a separately reviewed indexing/storage change.

Objects: at most 512 KiB each, 64 MiB and 2,000 active objects per tenant;
default retention 90 days, accepted interval 1–365 days. The operator creates
`AGO_OBJECTS_DIR` as a canonical private `0700` directory owned by the Linux
service user (image UID/GID 10001). Files are installed atomically with `0600`
permissions via no-follow directory descriptors; submitted paths and symlinks
cannot select a filesystem target. Native Windows private object operations
return unavailable; use the existing Linux service image for these adapters.
Unconfigured storage leaves all earlier workspace functions operational.

Operator commands (explicit local operations, never automatic HTTP execution):

```sh
python -m ago.storage_ops prepare-model --directory /private/ago-model --confirm
# Configure AGO_EMBEDDING_DIR=/private/ago-model after successful preparation.
python -m ago.storage_ops rebuild-index --tenant TENANT_UUID --confirm
python -m ago.storage_ops expire --tenant TENANT_UUID --confirm
python -m ago.storage_ops verify-objects --tenant TENANT_UUID
python -m ago.storage_ops backup-objects --tenant TENANT_UUID --destination /private/new-backup --offline --confirm
python -m ago.storage_ops restore-objects --tenant TENANT_UUID --source /private/new-backup --destination /private/new-restore --offline --confirm
```

Set `AGO_GRAPH_REDIS_URL` only for an existing trusted private Redis endpoint;
use authenticated TLS outside disposable CI. Cache entries have a 60-second
TTL, bounded size, tenant/version/query-specific keys and an HMAC bound to that
key. Node proposals/reviews and new edges bump the source version atomically
in PostgreSQL. Permission and verified-root checks precede any cache read.
Redis errors or invalid signatures fall back to PostgreSQL without activation
of a queue or grant cache. PostgreSQL alone remains fully operational.

Retention is explicit operator maintenance, not a running scheduler. Expired
objects are unavailable immediately according to database time even before a
cleanup run. Cleanup prioritizes active overdue metadata, retains tombstones
and safely retries missing files or interrupted cleanup. The application never
automatically deletes immutable reviewed graph/audit records. Process crashes
or caller rollback after installing a file can leave inaccessible orphan bytes;
operators must inventory and reconcile these against metadata while writers
are stopped. No automatic orphan deletion is enabled.

For coordinated recovery, stop application writers, back up every tenant's
active object manifest/bytes, then use existing `ago.release_ops backup` and
`verify-backup` to snapshot PostgreSQL during the same quiescent interval.
Retain the prepared model directory and its manifest separately. Restore the
database into an isolated `*_restore_drill` target before restoring objects into
a new private directory. Object restoration requires an exact match between
the backup manifest and the restored database metadata, and validates all byte
hashes before installation. A failed restore directory must be discarded by
the operator; never configure it as the active object root. Run object integrity,
graph traversal and semantic retrieval checks against the isolated target
before an independently authorized production cutover. There is no online
cross-provider atomic snapshot, multi-region DR or public deployment claim.

Dedicated CI runs the actual offline ONNX model, disposable PostgreSQL/Redis,
signed-session storage negatives and a populated database-plus-object recovery
drill. The ordinary Python matrix uses a clearly labelled injected test encoder
for API/persistence coverage; it is not substituted for real-model evidence.
Implementation acceptance logs were inspected for all nine successful jobs;
closing documentation commit CI is verified separately before final delivery.
