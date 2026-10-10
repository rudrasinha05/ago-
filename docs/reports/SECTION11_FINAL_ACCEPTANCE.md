# Section 11 — Personal local deployment acceptance

## Scope
Owner-approved personal localhost scope, documented in `docs/architecture/SECTION_11_LOCAL_DEPLOYMENT.md`. Original enterprise deployment requirements remain preserved and deferred. Implementation commit: `4a0e390` on `develop`.

## Local acceptance gates
| Gate | Evidence |
|---|---|
| Loopback-only startup with current schema and local environment | Existing guarded doctor/serve, plus actual start/health/shutdown test |
| Local health and failure alert | Bounded direct HTTP probes; status/body validation, latency and exit-code alert; redirect/malformed/oversized cases rejected |
| Recoverable database snapshot | Guarded local backup delegates to no-overwrite custom-format dump with verified SHA-256 manifest |
| Isolated restore | Local source/target validation plus separate empty `*_restore_drill`, transactional restore and schema verification |
| Optional safe container runtime | Existing unprivileged Docker image and loopback preview regression gate |
| Safe update/rollback and operator instructions | Windows commands, stopped-writer coordination, matching objects/code, no destructive live-database restore |
| Existing functionality preserved | Architecture/lint, database/browser/build/model/object-recovery CI gates |

## Verification
**Accepted for the owner's personal localhost scope.** All eight primary jobs and the independent backend job completed successfully; decoded logs were inspected. No skips in the three complete backend runs.

- Python 3.11, 3.14 and independent 3.12: **403 tests passed each**, including actual local AGO start/readiness/stop/failure-alert verification.
- Real local custom-format backup, checksum/manifest verification, separate empty PostgreSQL restore and restored schema verification passed through the new local operator commands.
- Actual model/Redis/storage checks: 31 passed; populated database, graph, semantic index and exact private object bytes recovered; mismatched manifests rejected.
- Existing Chromium journeys: six passed; cross-browser/accessibility matrix: 30 passed; real Next.js/PostgreSQL journeys: five passed.
- Docker non-root/loopback runtime smoke, three Next.js builds/HTTP exports, lint, SDK/console JavaScript and Sections 1–6/14 architecture guards passed.

Primary [38076341874](https://github.com/rudrasinha05/ago-/actions/runs/38076341874); independent [38076341820](https://github.com/rudrasinha05/ago-/actions/runs/38076341820), both at implementation `4a0e390`.

Local pre-CI targeted checks were 30 passed/3 PostgreSQL-dependent skips. The broad unconfigured local run had 321 passed, 81 skips and one database-readiness failure. Those runs were not used as full acceptance; the configured CI runs above supplied the required real PostgreSQL evidence.

## Limits
No new SQL migration or cloud resource. No evidence is claimed for testing this update on the owner's Windows machine, public deployment, production vault/TLS/encryption, hosted telemetry/on-call or external assessment. Database backups exclude external object bytes; matching object recovery is separately required when that store is configured. Local health checking is a one-shot operator command, not silently scheduled monitoring.
