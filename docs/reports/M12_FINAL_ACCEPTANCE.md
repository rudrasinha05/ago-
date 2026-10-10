# AGO M12 — Local Operator & Architecture Gap Audit Acceptance

**Status: M12 bounded code milestone accepted in GitHub CI.**
**Public release, full 0–35 blueprint and M0 historic parity: NOT accepted.**

## Verified CI reference

- Verified functional source commit:
  `d1d53d2afcc3ef553243dc4cc289a729efacc662`
- GitHub Actions run:
  https://github.com/rudrasinha05/ago-/actions/runs/38031369605
- Python 3.11: **254 passed, 0 failed, 1 preexisting Starlette warning**.
- Python 3.14: **254 passed, 0 failed, 1 warning**.
- Node 22: **14 passed, 0 failed** on each Python matrix leg.
- Real Chromium pilot: **6 passed, 0 failed** using live FastAPI and
  disposable PostgreSQL 16.
- Non-root constrained Docker image smoke: **passed**.
- Real PostgreSQL dump → SHA-256 manifest → empty restore drill: **passed**.
- Schema: migration files **001–018**; **M12 adds no new tables or SQL**.
- `python -m ago.local_ops doctor` emitted:
  `"database_local":true,"migrations_applied":true,"ready":true`
  on both CI Python versions, without printing credentials.
- Ruff, packaged-wheel UI contents: **passed**.

## M12 features implemented and accepted

1. Read-only `python -m ago.local_ops doctor`, checking safe dev/test
   environment, local PostgreSQL, migration digests and signing configuration.
   A missing *development* signing secret is represented as ephemeral-only
   on serve; a too-short configured secret is rejected.
2. `python -m ago.local_ops tenants` lists existing local tenant ID/name
   pairs without email, password or user role data.
3. `python -m ago.local_ops init` uses hidden interactive password entry,
   exact CREATE confirmation and one transactional creation of tenant,
   founder and distinct human reviewer. Existing tenants never overwritten;
   failure of reviewer signup rolls back newly created founder/tenant.
4. `python -m ago.local_ops serve` invokes the real server only on
   `127.0.0.1`, verifies the schema first and creates an ephemeral
   strong **development-only** signing key if none was configured.
   No automatic migrations, SQL cleanup, paid model calls or external tools.
5. Windows convenience `scripts/ago.ps1` supports doctor, tenants, init,
   serve, explicitly confirmed local migration and scratch-database test.
   Generated editable Python `*.egg-info/` is ignored without deleting files.
6. A usable Windows quickstart and explicit source-vs-blueprint gap register.
   No unverified original 0–35 section is silently relabeled complete.

## Mandatory negative scenarios exercised

- Remote, malformed or missing SQL URI is refused by doctor and onboarding.
- Explicitly production/staging operation is denied for local setup/launch.
- No available migrations or modified migration hashes fail readiness.
- One weak configured session key blocks server launch.
- Explicit action is required before creating accounts or applying migrations.
- Reviewer email cannot equal founder email; reviewer provisioning error
  leaves zero orphan new tenant/founder records.
- Startup binds loopback only; optional ephemeral session signing key
  remains in process memory and is never printed or written to disk.
- Doctor and tenant lookup never print database URI/password.
- Actual `python -m ago.local_ops serve` accepted a real HTTP
  `/console/` request on localhost with disposable migrated PostgreSQL.

## What is STILL open

- Historical M0/M0.1 source/document match to the founder's older Codex
  workspace was **not** independently verified; current M1+ CI is green.
- The original complete 0–35 blueprint is not present verbatim in the
  current GitHub repo; the condensed project handover is not full parity.
- Major proposed M13–M20 categories in
  `docs/ARCHITECTURE_STATUS_AND_BACKLOG.md` remain **unimplemented**.
- No local Windows founder terminal pull, physical device UAT or
  production cloud deployment was executed by GitHub code tools.
- Production MFA/SSO, realistic external connectors, marketplace, real
  financial settlements, fully autonomous workforce, distributed orchestration,
  secret vault, trusted public ingress, pentest, on-call and offsite DR remain
  separate engineering and human acceptance gates.

## Founder next action

After seeing all five CI gates green on the desired final commit, conduct
**one** fast-forward pull of `develop` onto their Windows workstation,
preserve any untracked files, verify the existing development PostgreSQL
and run the read-only M12 doctor. Use `tenants` if they already created a
company, `init` only if completely new, then `serve` and open
`http://127.0.0.1:8000/console/`. Passwords and DSN must not be shared
in conversation.

Details: `docs/reports/M12_LOCAL_QUICKSTART.md`.
Frozen scope: `docs/M12_SCOPE.md`.
Open research/commercial milestones: `docs/ARCHITECTURE_STATUS_AND_BACKLOG.md`.
