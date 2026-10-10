# Section 11 — Personal local deployment architecture

## Scope decision (2026-10-10)
The owner explicitly requires personal localhost use and does not currently want production deployment. This is an additive scope decision, not evidence that the original enterprise gates have passed. Section 10 implementation remains verified; its external vault, trusted production HTTPS/encryption and independent assessment gates are deferred until deployment. Preserve the original requirements.

Section 11 local acceptance covers loopback startup, failure diagnosis, health alerts, deliberate updates, recoverable backups and isolated restore. Kubernetes/Helm, public TLS, hosted telemetry and on-call are deferred. No infrastructure purchase or account setup is required.

## Runtime and boundaries
Windows: existing PostgreSQL 18 service, Python 3.11+, backend package and packaged same-origin console. Keep the existing organization and user IDs. `AGO_POSTGRES_DSN` stays in the operator environment; neither the launcher nor reports persist or print credentials. `local_ops serve` requires current checksum migrations, a localhost database and development/test stage; binds only 127.0.0.1. Its ephemeral session secret invalidates browser sessions on restart. Persistent application/database records survive restart. Independent review rules remain enforced even for a personal organization.

Docker Compose preview remains an optional separate local database, not a replacement for the existing Windows database. The unprivileged release image, loopback port mapping, internal network, dropped capabilities and read-only runtime are checked by existing CI. Do not mount an existing PostgreSQL 18 data directory into the PostgreSQL 16 preview container.

## Health and local alerts
`python -m ago.local_ops monitor --port 8010` probes actual liveness and readiness over direct loopback HTTP, with 3-second deadlines and 64 KiB response bounds. It ignores response details, refuses redirects and bypasses environment proxies. Both status codes and expected JSON status must agree. It reports healthy flags and latency; exit 0 means healthy, exit 2 is a local alert. It is a one-shot check: an operator can run it when needed; no background service or scheduled task is silently installed. Existing HTTP request IDs provide correlation; do not export account data or secrets into external logging tools. Production metric aggregation and distributed traces remain deferred.

## Update and rollback
1. Record `git log -1 --oneline` and stop the local server with Ctrl+C. Stop other AGO writers using this database too.
2. Create and verify a fresh backup; include the configured private object directory, if used, while all writers remain stopped.
3. Check clean working tree, fetch/pull the agreed develop branch, install the package and explicitly run migrations. No launcher runs migrations automatically.
4. Run doctor, start on the selected loopback port, run monitor in another terminal, then verify founder login and existing records. Schema version is checksum-validated.
5. If update fails, stop the server and preserve failed-version records for diagnosis. An older code checkout is safe only if compatible with the current schema. Never apply guessed reverse SQL or restore over the active database.
6. Recover the saved database into a separate empty `*_restore_drill` database, verify it, restore matching object bytes if used, and switch the local connection only after validation. Recover matching code revision too. Keep the original database until acceptance.

## Backup and recovery
`local_ops backup --output PATH --confirm` requires a ready local database and uses `pg_dump` custom format, exclusive no-overwrite output, SHA-256/size manifest and redacted failure reporting. Install PostgreSQL command-line tools matching or newer than the source server (Windows PostgreSQL 18 needs pg_dump 18+); add their bin directory to PATH. PostgreSQL credentials are passed through the subprocess environment, not command-line arguments.

`local_ops restore-drill --archive PATH --confirm` additionally requires both source and target DSNs to be localhost. Existing restore controls require a separate empty public schema and a database name ending `_restore_drill`; verify the archive before transactional restore and validate migration integrity afterward. The tool never creates or drops a database. Database snapshots do not include external private object bytes: back up and restore matching objects through the existing storage workflow before declaring recovery complete. Backup checksums detect corruption; they are not encryption. Keep backups in a private OS-protected directory, with disk encryption if desired, never Git. Choose backup frequency and retention according to personally acceptable data loss; no automatic deletion policy is enabled.

## Deferred original enterprise gates
| Original requirement | Current disposition |
|---|---|
| Reviewed Kubernetes/Helm/cluster deployment | Deferred until cluster deployment is wanted |
| Production metrics/traces/log aggregation/alerts | Deferred; bounded local health alert implemented |
| Trusted public TLS and rollout | Deferred; local update/rollback defined |
| Hosted backup/restore and on-call | Deferred; actual isolated PostgreSQL/object recovery covered by CI |

These are not checked off as completed. Local acceptance does not claim production certification or testing on the owner's machine after this update.
