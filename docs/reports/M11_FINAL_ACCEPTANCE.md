# AGO M11 — Real Browser Pilot Acceptance

**Result: M11 pilot application work ACCEPTED by isolated automated CI.**
**Not a public production deployment, external penetration review or manual
founder-device acceptance.** Existing M10 release blockers remain active.

## Source and measured proof — 2026-10-10

- Functional source commit:
  `400920c4c7cdbabfead78b0a14128b1d69bebf70`
- GitHub Actions workflow:
  https://github.com/rudrasinha05/ago-/actions/runs/38030395798
- **Python 3.11:** 236 passed, 0 failed, one nonblocking Starlette warning.
- **Python 3.14:** 236 passed, 0 failed, one nonblocking warning.
- **Node.js 22:** 14 UI security/state tests passed, 0 failed on both jobs.
- **Real Chromium:** 6 tests passed, 0 failed, against an actual live
  FastAPI server and a migrated disposable PostgreSQL 16 database.
- **Docker:** non-root, read-only runtime and same-origin UI/health smoke
  passed. **Disaster recovery:** real `pg_dump`, SHA-256 verification,
  isolated `pg_restore` and schema migration checks passed.
- All **five jobs succeeded**. No SQL migration, private account or public
  cloud resource was created by M11.

## Frozen gates accepted

1. **Real headless Chromium** using only disposable CI test accounts and
   PostgreSQL; failure screenshots/traceable errors, short-retention CI
   screenshot artifact. The real shipped browser modules execute.
2. **Founder journey:** authenticated UUID/email/password, all eight live
   workspaces, persistent strategic goals, explicitly captured executive
   evidence, bounded what-if simulation and server-revoked logout.
3. **Independent reviewer and end-to-end governance:** distinct human
   browser session; reviewer cannot create founder goals, propose council
   motions or enroll tools; a full goal → plan → draft step → plan approval →
   activation → task materialization → task approval → AI handler →
   independent QA journey executes with real HTTP and PostgreSQL.
4. **Mobile/accessibility smoke:** Chromium in phone-sized touch viewport;
   responsive nav drawer, native dialog keyboard focus/Escape, sign-in,
   client-side exception monitoring, safe/empty restricted workspace states.
5. **Acceptance evidence:** regressions verified on Python 3.11 + 3.14,
   Node UI tests, Docker and actual PostgreSQL backup/restore. Screenshot
   artifacts attached to the GitHub workflow with only generated test data.

## Discovered and fixed M9 integration defects

- M3 stored strategy state as `pending_approval`, but M9 previously
  expected `submitted`. The "Activate" button was unavailable even after
  an independent reviewer consented. The UI now joins existing M2 approvals
  and presents activation only for a matching approved request. The
  protected M3 activation API remains the final policy authority.
- Existing independent reviewer roles intentionally lacked `task:read`;
  therefore they could not see completed tasks in the general task table to
  finish human QA. Added `GET /v1/console/qa-queue` requiring `qa:read`,
  listing only unreviewed completed tasks in the current tenant. A separate
  `qa:review` grant is required to display the action and the backend still
  validates reviewer independence. Reviewer-wide task permission was **not**
  granted. SQL and UI regressions assert pending, reviewed, unauthorized and
  cross-tenant cases.

## What this evidence does *not* assert

- Full Chrome, Edge, Safari, Firefox compatibility; only Linux Chromium was
  tested. Mobile device touch events were simulated in Chromium, not
  verified on physical Android/iOS hardware.
- WCAG certification, a professional usability study, performance/load
  benchmarks, real-world egress audit or malware/penetration assessment.
- An actual autonomous company, self-improving AGI, live external API
  integrations or provider access; the internal handler is deterministic.
- Deployment at a public domain, signed production image promotion or
  hosting account controls. M10's domain/TLS, external secrets, access
  controls, monitoring/on-call, disaster recovery and legal/security
  production gates remain externally operator-owned.
- M9/M10/M11 have **not yet been pulled into the founder's Windows copy**;
  local browser signoff must be conducted after a single explicitly
  founder-requested pull.

Frozen scope: `docs/M11_SCOPE.md`.
Pilot operating guide: `docs/reports/M11_PILOT_OPERATOR_GUIDE.md`.
No intermediate Windows pull is required or performed during this milestone.
