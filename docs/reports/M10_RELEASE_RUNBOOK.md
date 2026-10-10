# AGO M10 — Security & Release Engineering Operator Runbook

**Classification:** Release candidate engineering, not automatic production clearance.
**Source:** GitHub `develop`, M1–M10 modular monolith, PostgreSQL 16 verified
in CI and Windows local M1–M8 historically tested. M9 and M10 browser and
Windows acceptance remain to be completed only after a founder-requested pull.

## 1. Proven deployment boundaries

- App and control center use one origin. The UI at `/console/` has no CDN,
  build-time secrets or third-party script execution.
- Dockerfile `deploy/docker/Dockerfile` ships the Python wheel, UI and
  existing `deploy/sql` migrations; UID/GID 10001:10001, no root runtime.
- Image defaults to **production mode** and refuses to start without verified
  secrets, allowed public domain(s), certificate-validated PostgreSQL and
  disabled optional egress. **The Docker default is deliberately unusable
  for an unconfigured public launch.**
- Explicit `python -m ago.event_runtime migrate` is a separate, privileged
  operator action; service startup NEVER runs migrations.
- `/health/live` only means the process is serving requests;
  `/health/ready` requires responsive PostgreSQL and, in production, exact
  migration hashes. Do not use liveness as a traffic-admission signal.
- Business requests in production require HTTPS as reported by a *trusted
  proxy* or a direct TLS-terminating ASGI server; plain HTTP returns 426.
  Health-only internal probes are exempt. App validates the forwarded host
  against an explicit public hostname allowlist.
- Production docs/OpenAPI endpoints are not served. Bearer auth and
  independent M2 human governance remain effective. Responses use
  no-store headers, browser CSP and safe correlation IDs; body cap includes
  chunked inputs. This **does not replace an ingress WAF/rate limit**.

## 2. Required real operator infrastructure before public release

1. Approved organization domain and trustworthy DNS with ownership review.
2. Valid HTTPS certificate and a gateway/load balancer that strips all
   incoming `Forwarded`/`X-Forwarded-*` client headers, injects its own
   trusted forwarding headers, enforces HTTPS redirects and HSTS, and has
   host allowlists, request-rate and body-size limits.
3. Configure **only** known proxy IPs as Uvicorn's `--forwarded-allow-ips`
   when the gateway is installed. **Never set `*`**, never trust all
   public clients. The default image explicitly uses `--no-proxy-headers`
   and therefore fails closed on public business requests.
4. Certificate-validated PostgreSQL URI with `sslmode=verify-full` and
   `sslrootcert`, managed secrets, private network, separate **migration
   owner** and **runtime application** DB roles, minimal table permissions.
   Project migrations currently assume a high-privilege owner; role
   separation and database permissions must be individually reviewed
   and tested before launch.
5. External M8 telemetry and paid models explicitly **disabled**. The
   external provider adapter has not passed DNS-rebinding/network egress
   certification; open outbound access is forbidden without a new review.
6. Secret rotation/revocation, at-rest encryption, off-site backups,
   recovery keys, on-call telemetry and alert thresholds.
7. Disaster-recovery exercise on separately isolated infrastructure with
   recovery time/objective targets, plus manual Chrome/Edge/mobile visual
   acceptance, accessibility audit, load/penetration tests and signoff.

**None of these external production prerequisites can be certified just by
CI code tests. Do not turn on public DNS until they pass.**

## 3. Production configuration preflight

Set the following **in a protected process environment** (never in GitHub
comments/commits or chat):

- `AGO_ENVIRONMENT=production`
- `AGO_SESSION_SECRET`: at least 48 bytes, high entropy, not a template
- `AGO_ALLOWED_HOSTS`: comma-separated full public DNS hostnames, no
  wildcard, IP literal, local or test domain
- `AGO_POSTGRES_DSN`: `postgresql://...` including
  `sslmode=verify-full&sslrootcert=/path/to/trusted_ca.pem`
- `AGO_MIGRATIONS_DIR`: container path `/app/deploy/sql` for wheel deploy
- `AGO_ENABLE_PAID_MODELS=false`,
  `AGO_M8_EXTERNAL_ENABLED=false`, `AGO_DEBUG=false`

See `deploy/docker/production.env.example` for *non-deployable* names.

**After the privileged DBA has explicitly applied backed-up and reviewed
migrations:**

```powershell
python -m ago.release_ops check
```

The CLI emits only JSON booleans:
`configuration`, `schema`, `external_egress_disabled`, `passed`.
Exit code 0 means these *bounded preconditions* are satisfied, not a security
audit. Exit 2 means fail closed. **It never prints DSNs or secret values**.

## 4. Local loopback preview and image lifecycle (operator-initiated)

For a local-only demonstration, generate strong preview-only secrets locally.
The preview compose binds API to `127.0.0.1:8000` and publishes no
PostgreSQL port. It is **not** a production stack. From repo root:

```powershell
docker compose -f deploy/docker/compose.preview.yml build
docker compose -f deploy/docker/compose.preview.yml up -d postgres
# Explicit, reviewed preview database migration; NEVER auto-migrate production.
docker compose -f deploy/docker/compose.preview.yml run --rm api python -m ago.event_runtime migrate
docker compose -f deploy/docker/compose.preview.yml up -d api
```

The variables `AGO_PREVIEW_DB_PASSWORD` and
`AGO_PREVIEW_SESSION_SECRET` are required in the calling environment
and cannot be default/empty; never reuse production secrets.
Open `http://127.0.0.1:8000/console/` after successful health checks,
using a separately bootstrapped dev tenant.

Build the image from repository root:

```powershell
docker build -f deploy/docker/Dockerfile -t ago-m10:local .
```

Check image UID, production-default configuration and migration bundle
before promotion. Publish only immutable image digests approved by the
operator. Roll back **application image only** after governance review; do
not roll SQL migrations backwards automatically because data may have
changed. Execute a post-rollback compatibility check before re-opening
user traffic.

## 5. Backup and isolated restore drill (human action; real CI exercised)

Prerequisites: `pg_dump`/`pg_restore` PostgreSQL client tools,
`AGO_POSTGRES_DSN` and an explicitly isolated
`AGO_RESTORE_TEST_DSN`, ending with database name `_restore_drill`.

```powershell
# Choose an encrypted, access-restricted filesystem outside the git repository.
python -m ago.release_ops backup --output "<SECURE_BACKUP_PATH>\ago.dump" --confirm
python -m ago.release_ops verify-backup --archive "<SECURE_BACKUP_PATH>\ago.dump"
python -m ago.release_ops restore-drill --archive "<SECURE_BACKUP_PATH>\ago.dump" --confirm
```

Backup writes custom PostgreSQL `PGDMP`, mode 0600 where supported, and a
separate SHA-256 + byte-count manifest. Existing targets and symlinks are
rejected; partial dumps are deleted. Restore drill requires the explicit
flag, a distinct `*_restore_drill` database, empty target public schema,
checksummed manifest, `--single-transaction` and `--exit-on-error`. It
checks migration hashes on restored data and **never uses --clean or
--create**. Failure leaves the operator responsible for discarding the
disposable drill database. The backup contains potentially **sensitive
enterprise information**; encrypt and restrict it, and follow lawful
retention policies.

**Rehearsing a restore on CI's disposable DB is not equivalent to a
cross-region disaster-recovery exercise.** Cross-region snapshot validity,
key escrow and real-world RPO/RTO remain independent gates.

## 6. Release acceptance register

| Gate | CI-owned and automatable | External operator-owned |
|---|---|---|
| Python/PostgreSQL security regressions | Yes | Production penetration test |
| Node UI code contracts and package contents | Yes | Visual accessibility and UX signoff |
| Linux non-root container and loopback HTTP smoke | Yes | Domain, TLS gateway and hosting |
| Exact migrations & in-container SQL files | Yes | Privilege-separated prod schema owner |
| Dump/checksum/empty-DB restoration | Yes | Encrypted off-site retention and DR time tests |
| Account/session/RBAC/cross-tenant logic | Yes | Tenant invitation lifecycle and MFA |
| Host, HTTPS, body cap, no-store behavior | Yes | Ingress WAF, public rate limits, DDoS plan |
| Graceful failure and manual rollback plan | Partially | Production maintenance window/on-call |

Any incomplete external row means **public production release not approved**.
Retain immutable CI run URL, Git commit, SHA digest and signed release
decision by the actual owner in a separately access-controlled change
record. M10 evidence is in `docs/reports/M10_FINAL_ACCEPTANCE.md`.
