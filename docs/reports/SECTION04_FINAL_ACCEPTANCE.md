# Section 4 — Folder / Monorepo Architecture Acceptance

Scope: seven current master-checklist requirements. Baseline `b6de17b`.
Original full blueprint unavailable; no exact-source-parity or complete frontend claim.

- [x] Preserve version-controlled FastAPI backend and integration/browser tests.
- [x] Build and serve actual Next.js web shell.
- [x] Build and serve admin/docs shells; API launcher forwards to existing backend.
- [x] Create all seven approved service boundary directories with checked module maps.
- [x] Create private shared UI, typed health SDK and shared contracts.
- [x] Provide infrastructure/deployment/monitoring/test/script/CI directory ownership.
- [x] Enforce workspace roster, dependencies, relative import boundaries and service maps.

Local boundary/Ruff tests: passed; five new Python negative/positive tests;
three SDK origin/timeout/privacy tests passed. All three optimized application-shell builds and actual loopback HTTP exports passed.
Implementation commit `4845502`, primary CI [38037327542](https://github.com/rudrasinha05/ago-/actions/runs/38037327542) and independent backend CI [38037327626](https://github.com/rudrasinha05/ago-/actions/runs/38037327626) passed.
All six primary jobs passed: Python 3.11/3.14 (298 tests each), 14 console JS,
six Chromium journeys, nonroot Docker, real PostgreSQL restore, and three
Next.js production builds with served-export smoke plus three SDK tests.
Closing commit `ee76a41` passed all six primary jobs in [38037489301](https://github.com/rudrasinha05/ago-/actions/runs/38037489301) and independent backend [38037489284](https://github.com/rudrasinha05/ago-/actions/runs/38037489284) before Section 5 began.
The HTTP smoke initially caught a missing local web export; rebuilding that workspace
restored the homepage, and all three served outputs then passed. Dependencies use exact versions and committed lockfile; no new deployed service,
database, private frontend authority or schema change. Full Section 6 UI and
Section 34 SDK are independently outstanding. Rollback reverts this scaffold.
