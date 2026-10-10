# Section 6 — Frontend Architecture Acceptance

Frozen scope: all eight supplied Section 6 requirements, baseline `c04df79`.
All eight gates are CI-accepted. Full original blueprint fidelity remains
unverified; physical-device/assistive-technology certification is not claimed.

- [x] Preserve responsive eight-workspace console and governed operations.
- [x] Ship a working Next.js App Router frontend, packaged on the API origin.
- [x] Define router, tab-memory session and stale-request-safe data architecture.
- [x] Supply shared React design components and canonical compatibility adapters.
- [x] Provide executive, department and employee dashboards using authorized records.
- [x] Preserve signed sessions, backend RBAC and independent approval interfaces.
- [x] Pass live API Chromium acceptance for the Next.js frontend.
- [x] Pass bounded Chromium/Firefox/WebKit, mobile/tablet, keyboard and axe checks.

Accepted implementation: `86d85cd57f7d7a72d694d797e9d53624b48430bd`.
Primary CI [38051813820](https://github.com/rudrasinha05/ago-/actions/runs/38051813820)
and independent backend CI [38051813819](https://github.com/rudrasinha05/ago-/actions/runs/38051813819)
passed; all eight job conclusions and decoded acceptance logs were inspected.

| Gate | Verified result |
| --- | --- |
| Python matrix and independent backend | 326 passed each on 3.11/3.14/3.12; no skips |
| Console JavaScript / SDK | 14 / 8 passed |
| Existing live Chromium console | Six independent journeys passed |
| Next.js browser/device compatibility | 30 passed across six Chromium/Firefox/WebKit desktop/phone/tablet projects |
| Accessibility | WCAG 2.1 A/AA axe scans, keyboard dialog/Escape, focusable scroll regions, responsive layout; zero scoped violations |
| Actual Next.js / signed session / PostgreSQL | Five passed, including persisted goal, reviewer restrictions, mobile dashboard, two-human approvals/execution/QA and nonapplying Digital Twin |
| Production exports | All three optimized builds and actual served homepages passed |
| Release | Wheel contains Next routes/chunks/bootstrap hashes; nonroot Docker serves `/workspace/` and `/console/`; anonymous APIs remain closed |
| Recovery and architecture | Actual PostgreSQL checksum/restore drill; migrations, all Section 1–6/14 guards and Ruff passed |

The Next.js static export runs within the existing Python service. React owns
router, session, async state, shell and dashboards; existing governed workflows
use explicit escaped compatibility render/action adapters from canonical shared
packages. There is no iframe, cross-origin permission, new database/service,
SQL migration, public deployment or paid-provider activation.

Regression checks caught selected-button hover contrast, mobile table keyboard
scrolling and unmanaged Digital Twin input events. The fixes are covered by the
browser matrix and actual simulation journey; edited threshold values reach
simulation, while live DNA versions remain unchanged. Session clearing aborts
pending reads and rejects stale responses; logout drops local authority
immediately and revokes the captured server session. No tokens persist in browser
storage, cookies, route URLs or exported HTML. Style attributes are explicitly
allowed by workspace CSP; scripts require self or exact static bootstrap hashes.

Local verification also passed all source guards, actual wheel/exports, Ruff,
14 console JS, eight SDK and ten Chromium desktop/phone journeys. Full local
Python: 265 passed, 60 DB-dependent skips and the established readiness failure
because this host has no PostgreSQL DSN/server. A source-copy test raced with
concurrent generated output, then passed after builds completed. These gates
passed against real PostgreSQL in CI; local WebKit dependency/Firefox startup
limits were resolved by the CI browser environment. Desktop/phone screenshots
were visually inspected. Physical founder Windows/mobile UAT remains separate.

Rollback: revert the section as a unit and rebuild the prior image; no database
rollback. `/console/` remains operational. See SECTION_06_FRONTEND_ARCHITECTURE.md
for packaging/operator commands. Final closing documentation commit CI is
verified before delivery. All other unfinished sections remain independently
tracked; this acceptance does not mark Sections 7–34 complete.
