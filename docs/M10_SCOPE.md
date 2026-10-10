# AGO M10 — Release Engineering & Production Safety Gates (frozen)

M10 is a **production-conscious release-candidate engineering milestone**, not
permission to publish or claim real-world enterprise security certification.
Keep the M1–M9 modular monolith, PostgreSQL and same-origin web UI unchanged.
Work on the single `develop` branch.

## Six frozen M10 gates

1. **Fail-closed production configuration** — `AGO_ENVIRONMENT=production`
   requires a long non-default HMAC secret, explicit trusted public hostnames,
   TLS-verified PostgreSQL DSN and disabled optional external M8 egress.
   Production OpenAPI/docs and developer tracing are not exposed.
2. **HTTP perimeter & safe probes** — trusted-host rejection, HTTPS-only
   production business requests, no-store on private API, strict security
   headers, bounded JSON request bodies including streamed/chunked requests,
   safe request ID correlation, independent /health/live and migration-aware
   /health/ready which never leak credentials.
3. **Reproducible deploy artifacts** — deterministic application build
   using source-controlled Dockerfile, multi-stage non-root runtime, explicit
   SQL migrations and packaged UI assets, local-only compose preview, Docker
   ignore/secrets rules. Migrations run explicitly before starting services.
4. **Backup/restore disaster-recovery tooling** — operator-initiated logical
   PostgreSQL custom-format dump, SHA-256 manifest, integrity/list verification
   and *isolated* empty restore-drill with explicit consent and target suffix.
   Fail closed on checksum mismatch and same-database restore; no automatic
   production overwrite.
5. **Release health and operations** — headless `release check` CLI checks
   secrets, DSN safety, migration checksums, external egress policy and build
   fingerprints, emits a machine-readable result without credentials; staged
   operator runbooks cover rollback, drill, TLS termination, alerts and
   separate manual release signoffs.
6. **Automated release gates** — Python 3.11/3.14 + PostgreSQL CI carries
   forward all M1–M9 tests and Node UI tests, adds adversarial production
   HTTP/config/schema checks, CLI unit tests, wheel and Docker build smoke
   (where supported by hosted CI); never marks actual deployment/security
   audit as passed without evidence.

## Explicitly NOT M10-complete automatically

Actual cloud registration/domain/DNS/TLS certificate, enterprise secret vault,
least-privileged production database account, externally attested backup/
recovery targets, routine monitoring/on-call, provider security pen test,
load/chaos certification and manual Chrome/Edge/mobile user acceptance are
**external operator release gates**. "CI-accepted M10" means implementation
and bounded internal tests accepted, **not production deployed or guaranteed
release-ready**. No user-secret values in GitHub, requests or logs.

BDR: architecture freeze, consolidated milestones, founder local pull only on
their explicit next instruction.
