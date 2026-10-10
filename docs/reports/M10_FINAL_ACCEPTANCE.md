# AGO M10 — Release Engineering Acceptance / Public Launch NOT Authorized

**Status: M10 software release-candidate gates ACCEPTED in isolated GitHub CI;
public production deployment remains BLOCKED on operator-owned controls.**

This report distinguishes code/CI acceptance from actual production suitability.
AGO's AI-native organizational ambitions are **not** equated with a certified
autonomous general intelligence, a security audit or a publicly deployed service.

## Independently observed functional evidence

- Full Python/JavaScript + image + DR acceptance at commit
  `7b86e62475a34082326fbd00d64ef73cff232f41`.
- GitHub Actions run:
  https://github.com/rudrasinha05/ago-/actions/runs/38022635888
- Python 3.11: **236 passed, zero failed, one nonblocking warning**.
- Python 3.14: **236 passed, zero failed, one nonblocking warning**.
- Node.js 22: **13 UI tests passed, zero failed** on each Python CI job.
- PostgreSQL 16: migrations **001–018**, including checksum-aware verification.
- Ruff + Python wheel containing the actual M9 console: **passed**.
- Dockerfile: non-root UID/GID 10001, production-default startup safety,
  `/console/` static UI and health/unauthenticated HTTP smoke: **passed**.
- Disaster recovery gate: **real PostgreSQL client binary** produced a custom
  dump, verified its SHA-256, restored into an empty separate
  `ago_restore_drill` database, and re-validated SQL migration integrity.
- Subsequent hardening restricts Docker to read-only root filesystem,
  zero Linux capabilities, no privilege escalation, bounded memory/pids;
  a later dedicated image smoke validated this as well.
- This release gate does not delete or migrate any founder workstation files;
  work remains on the single `develop` branch.

## Six M10 gates

1. **Fail-closed production configuration:** requires strong signing key,
   reviewed public FQDNs, certificate-verified PostgreSQL, disabled paid and
   external provider egress; no production auto-debug or public API docs.
2. **HTTP perimeter:** reject non-HTTPS production business requests,
   trusted-host validation, 1 MiB maximum production body including streamed
   data, HSTS on HTTPS, no-store on tenant APIs, CSP and safe request IDs.
3. **Build/deployment:** source-controlled wheel/image, included 18 migration
   files, unprivileged container, local-only preview compose, no automatic
   migration or default real production credentials.
4. **Disaster recovery:** consent-required private PostgreSQL backups, custom
   PG archive, SHA-256 manifest and tamper rejection; consent-required
   empty disposable restore drill with no destructive `--clean` operation.
5. **Operational release checks:** redacted machine-readable
   `python -m ago.release_ops check` which refuses nonproduction mode,
   missing config and migration checksum mismatches; monitored live/ready
   states and documented safe rollback procedures.
6. **Full automated evidence:** regressions across previous milestones,
   adversarial ingress/config, role/auth, backup/restore, Docker and JS tests
   in independently isolated CI jobs.

## Release risk register — not yet signed off by founder/operator

- Actual cloud vendor/account, domain, DNS ownership and TLS certificate.
- Trusted reverse proxy, rate limits, DoS protection and non-public DB access.
- Secret manager, key rotation, least-privilege database account, tamper-proof
  external audit logs and verified alerting/on-call procedures.
- Encrypted offsite backups, scheduled cross-region restore rehearsal and
  measured recovery objectives.
- Production vulnerability/penetration assessment and SaaS provider egress
  controls (external metrics/paid model disabled by default).
- M9 Control Center visual/browser/keyboard/device UAT on founder's machine,
  with real operator and independent reviewer accounts.
- Operational acceptance: image promotion/signature, load/capacity tests,
  maintenance rollback exercise, regulator/privacy declarations as applicable.

**Consequence:** Do NOT claim public production is "100% release ready" or
automatically deploy AGO. The repository is a CI-verified software release
candidate and an operator-run local/staging preview only.

### Paths

- Frozen scope: `docs/M10_SCOPE.md`.
- Operator safety, backup/restore and staged hosting:
  `docs/reports/M10_RELEASE_RUNBOOK.md`.
- Deployment package: `deploy/docker/Dockerfile`,
  `deploy/docker/compose.preview.yml`.
- Migration executor: `python -m ago.event_runtime migrate`.
- Release checker/backup/restore CLI: `python -m ago.release_ops`.

No intermediate Windows pull was requested. The founder decides when to
perform **one** consolidated M9–M10 sync and local visual acceptance.
