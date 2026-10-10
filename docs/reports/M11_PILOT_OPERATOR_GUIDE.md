# AGO M11 — Pilot Browser Acceptance Operator Guide

M11 is a **live-browser validation and usability hardening** milestone for the
existing M9 Control Center on top of the CI-verified M10 release candidate.
It does not authorize public DNS, production billing, outside organizations or
unreviewed autonomous tool operations.

## What the pilot verifies

A dedicated GitHub Actions job uses **real headless Chromium** against a
running Uvicorn/FastAPI server and a migrated **disposable PostgreSQL 16**
database. The tests provision distinct founder and independent reviewer human
identities. They do not use fake API responses or inject bearer tokens into
the browser.

Tests cover:

- Founder logs in using organization UUID, email and password; real HTTP
  calls load all eight Control Center workspaces.
- New strategic objective saved to PostgreSQL and still visible after refresh.
- Evidence snapshot captured explicitly, what-if threshold run against
  unchanged organizational DNA; simulation is not activation.
- Reviewer has a separate real signed session and cannot use founder creation,
  council proposal or tool enrollment controls.
- Founder signs out; exact server session revocation succeeds and browser
  refresh requires re-authentication; no local/session storage or cookies hold
  the token.
- Mobile-size Chromium viewport, navigation drawer, native accessible dialog
  and Escape close.
- Two human end-to-end governance flow: founder registers AI employee and
  creates goal/plan/step; independent reviewer approves the strategic plan;
  founder activates/materializes and requests task approval; reviewer approves
  execution; founder dispatches deterministic internal AI handler; separate
  reviewer performs QA through an **independently scoped Pending QA queue**.

The test harness keeps CI-only founder/reviewer accounts and disposable
test-generated data. Screenshots are uploaded as a short-lived GitHub Actions
artifact, including failures. Never use production customer data in this job.

## Key fixes against M9

1. UI now reads the actual backend plan state `pending_approval` rather than
   a non-existent `submitted` value. Activation is surfaced only after
   matching independent approval, although the backend remains authoritative.
2. Authorized QA reviewers without broad `task:read` access now receive a
   narrow, tenant-filtered `GET /v1/console/qa-queue` covering only unreviewed
   *completed* tasks. No role escalation and no automatic QA verdict.
3. Browser tests assert real HTML/JS behavior and document actual screenshot
   evidence instead of assuming Python/Node unit tests cover click paths.

## For founder's Windows environment — AFTER explicit request to pull

M9 and M10 were not pulled locally when M11 began. No automatic local
repository, database, user, password, permission or deployment changes happen
as a result of GitHub tests.

When the founder requests sync, preserve local untracked files and review
the existing Git state first, then perform one fast-forward pull of
`develop`. Use the previously configured development/test DSNs (never
production for testing). Run the full Python and Node tests, start
`python -m uvicorn ago.main:app --host 127.0.0.1 --port 8000` from
`apps/backend` and visit `http://127.0.0.1:8000/console/`.

To reproduce the browser pilot locally, install Node only for its separate
unit tests and install `playwright==1.55.0` plus Chromium for Python browser
tests; run `python -m pytest -q tests_browser` using a disposable, already
migrated database. The browser tests **create new tenant and human identities**
in the configured test database and start a local server on port 18771.
Do not run against real customer data.

## Final exclusions and operator acceptance

CI Chromium screenshots and keyboard smoke tests do not replace real manual
Chrome/Edge/mobile device inspection, independent accessibility audit, visual
review of typography/responsiveness, network failure chaos/load testing or a
production penetration test. The M10 external release blockers remain open.
There is **no public production deployment** or new paid/third-party connector.

Frozen scope: `docs/M11_SCOPE.md`. Final CI and artifact references:
`docs/reports/M11_FINAL_ACCEPTANCE.md`.
