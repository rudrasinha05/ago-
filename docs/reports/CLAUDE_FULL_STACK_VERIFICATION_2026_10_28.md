# AGO full-stack verification — Claude, 28 October 2026

Founder request: verify AGO start to end, frontend and backend, and correct
errors, mistakes and anomalies. This complements JARVIS's
[FULL_STACK_AUDIT_2026_10_28.md](FULL_STACK_AUDIT_2026_10_28.md) (`d0a3b5f`)
and does not repeat its fixes. Claim and coordination: Issue #4.

## How it was checked

| Check | Result |
|---|---|
| Backend `pytest` with **real PostgreSQL 16** (all 65 migrations, CI env) | see Verification |
| `tests_next` (real PostgreSQL + server + Chromium) in UTC **and** in the sandbox's IST timezone | 12/12 both (after fix 5) |
| Ruff (CI scope), Section 1–6 and Section 14 architecture/contract checks | pass |
| Extended bug lint (bugbear, SQL-string, blind-except, timezone) on `ago/` + `scripts/` | 41 reports reviewed, no defect (below) |
| ESLint with React hooks rules on `apps/web`, `packages/sdk`, `packages/ui` | 0 errors; 16 warnings reviewed |
| Frontend → backend contract: every `api.request` call site matched to a real route | 125 call sites; 1 unmatched by design |
| HTML injection sinks (`innerHTML`, string views) | all dynamic values go through `safe()` |
| SDK node tests, `tests_web`, Next.js builds (web, admin, docs) | pass |
| Playwright, 6 browser/device projects + company map script (mocked API) | see Verification |
| **Live end-to-end run**: real backend + PostgreSQL + Chromium, Founder and Reviewer | below |

The live run is new: it signs in as a real Founder and an independent
Reviewer on a fresh local company and clicks through all 8 workspaces, every
Organization tab, departments, roles, chat, map views, Board appointment,
project brief → submit → Founder approval → Execution Desk, recording every
HTTP ≥ 400, console error and page error. Mocked tests cannot find
integration defects; this run found three (items 2, 3, 6).

## Defects found and corrected

1. **CI red after the Organization tabs commit (my mistake, `a1b0c69`).**
   Two backend tests that read frontend source failed in Backend quality and
   foundation-through-m12. I had run Playwright and the map script but not
   those tests. Fixed in `d664d98` by improving the code, not the tests: the
   Board is its own `CompanyBoard` component (one `CommandBrain` again) and the
   Projects / Execution & Delivery tabs show jump links only for sections the
   role can see. CI green on `d664d98`. All 8 backend test files that read
   frontend source are now part of my pre-push routine.
2. **Forbidden resources polled forever.** A Reviewer (no `task:read`,
   `messages:read`, `organization:read`, `tool:read`) on the Organization page
   re-requested chat every 5 s, activity and notifications every 7 s, plus
   governance, reports and the tool catalog — an endless stream of 403s. Polls
   now start only when the role holds the read permission the API requires;
   one-shot workspace reads still show explicit "denied" states (Section 6
   contract). Browser test: no forbidden poll in 8 s.
3. **Map shifted irreversibly on keyboard focus.** Focusing a card outside the
   visible map made the browser scroll the clipped canvas, displacing the whole
   map with no way back; in the live run the Founder's "Talk to your company"
   box became unreachable after hiring a role. Focus now pans the map to the
   card and any canvas scroll is converted into a pan. Browser test on all 6
   projects.
4. **Department names: domain rule not enforced in PostgreSQL.** The domain
   model rejects "engineering" after "Engineering", but the table constraint
   is case-sensitive, so the database accepted both; an exact duplicate
   returned a generic "Database conflict". The store now enforces the domain
   rule and returns "A department with this name already exists" (HTTP 400).
   Failing-first PostgreSQL test. (Small backend change in
   `organization_store.py`; no schema or API shape change.)
5. **`tests_next` failed on any machine whose browser timezone differs from
   Python's** (e.g. an India-time founder machine): the emergency-stop test
   typed a Python-clock time into a browser-local `datetime-local` field. The
   value is now produced with the browser's own clock. Passes in UTC and IST.
6. **Stale project status after approval.** After the Founder approved a plan
   in Approvals, the Projects tab still said "Founder approval needed". The
   status now follows the recorded plan state while a decision is pending.
7. **Flaky skip hid the 3D test path.** WebGL-dependent tests checked for
   WebGL before the scene had reported, so WebKit sometimes skipped the 3D
   pointer path silently. The scene now exposes `data-webgl=pending|on|off`
   and tests wait for a decision.
8. **Test fixtures did not match the real Founder role** (writes without the
   matching reads). Fixtures now mirror the real Founder permissions.
9. **Unstable `departments` identity** rebuilt map layout and colour memos on
   every render when departments were unavailable. Memoised.

## Reviewed, no defect

- 15 string-built SQL statements: every interpolated identifier comes from a
  fixed allowlist; all values are parameters.
- 5 "loop variable not bound" lint reports in `company_chat.py`: the closure
  is called inside the same iteration.
- Blind `except Exception` sites: shutdown/cleanup/readiness probes.
- Frontend calls: all match backend routes except
  `POST /notifications/read`, which the UI only calls after the server
  advertises a read cursor (handoff pending).
- Founder approval without an appointed AI CEO returns 403 from
  `/ceo/reconcile`; by design, and the UI shows "CEO handoff incomplete".

## Handed off (contracts, not edited)

- Issue #4: `GET /v1/security/sso/session` answers 401 on every page load when
  no SSO cookie exists, logging a console error for every password user.
  Requested 204 for "nothing to redeem".
- Issue #4 (earlier): durable per-user notification read cursor.

## Verification (local, after all fixes)

- Backend: **1280 passed** with real PostgreSQL (CI environment variables,
  UTC), coverage 87.2%, engineering quality gate passed; ruff clean.
- `tests_next`: 12/12 in UTC and in IST.
- Playwright: **120 passed**, 6 intentional skips (wheel/mouse tests on touch
  projects; WebGL zoom where the browser has no WebGL); company map script
  PASS including WCAG; all 8 backend tests reading frontend source pass.
- Live Founder run: every step passes; remaining HTTP ≥ 400 are the SSO probe
  (handed off), the deliberate duplicate-department check (now a clear 400)
  and the by-design 403 when no AI CEO is appointed.
- Live Reviewer run: only one-shot explicit workspace denials remain; no
  repeated polling of forbidden resources.

## Known gaps (not defects)

- Ops scripts outside CI lint scope have 4 style findings (lambda
  assignment).
- Lowest coverage: CLI ops `message_ops.py`, `storage_ops.py` (0%) and
  `m6/m7/m8_permissions.py` (37%).
- JARVIS's report lists the scope and acceptance gaps (17 sections tested,
  13 partial, owner-device evidence outstanding); unchanged here.
