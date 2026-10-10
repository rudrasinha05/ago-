# Section 6 — Frontend Architecture (Next.js)

Scope is all eight supplied checklist gates. Full original blueprint fidelity
is unverified; this section does not add account provisioning, enterprise SSO,
third-party marketplace or production device certification.

## Runtime and router

`apps/web` is a real Next.js App Router application. Eight static routes under
`/workspace/` implement overview, strategy, governance, organization, knowledge,
operations/tools, calendar and digital twin. Next Link navigation and direct
URL reloads work. Root layout retains one React session provider across routes;
reload intentionally requires sign-in. Error/not-found boundaries have safe
recovery navigation. React owns shell/navigation, login, async data state and
three dashboard experiences. Eight existing workflow renderers/actions are
explicit compatibility adapters in `@ago/ui`, with escaped backend strings.
They are neither an iframe nor a new authorization implementation.

`next build --webpack` creates a static export. `scripts/package_frontend.py`
copies that reproducible output into the Python wheel. The existing FastAPI
process serves it on the API origin; production Docker uses a Node build stage
but the nonroot runtime still has one Python service, no Node runtime/server.
No CORS permission, reverse-proxy service or database is introduced.

## Data, identity and mutation architecture

`@ago/sdk/session` is the sole authenticated same-origin transport: bounded
requests, private token, no browser persistence/cookies, no redirects, no
foreign origins. Session clearing aborts outstanding requests and generation
checks reject stale responses even if a fetch implementation ignores abortion.
`SessionProvider` validates current-member identity, preserves exact passwords,
handles expiry and explicitly revokes logout sessions. No secrets go into URLs,
Next server components, exported HTML, React route state or local/session storage.

`@ago/sdk/workspace` defines one authorized read plan per route. Parallel
resources independently report ok/forbidden/unauthenticated/error. Restricted or
failed resources are shown as unavailable rather than fabricated zero metrics.
Department employee fan-out validates identifiers and propagates denial.
Workspace read epochs reject stale navigation/refresh/session results. Mutation
contexts bind to the active page and session generation, preventing old dialogs
from issuing follow-up writes through a different member's session. Dialog
close/backdrop/Escape behavior uses native focus-trapping semantics.

Existing `/v1` routes remain authoritative for signed session validity, active
human identities, tenant isolation, permissions, independent approvals, task
states, audit and QA. Button visibility and dashboard selection are presentation
only. No automatic writes occur during reads, route changes or simulations.
After explicit mutations the current route refreshes from actual backend records.

## Shared design system and experiences

`@ago/ui/components` supplies semantic Button, Field, Notice, Panel, Metric,
Records and Loading primitives. `workspace.css` holds shared design tokens,
responsive tables, forms, panels, native dialogs and reduced-motion styles.
The app adds responsive navigation, focus indication, skip link, semantic
landmarks, live notices and selected-state contrast. Wide record tables have
keyboard-focusable scroll regions. `sprite` is static first-party icon markup.

Executive dashboard displays authorized task and pending approval summaries.
Department dashboard selects an authorized department and derives task counts
from its actual employee assignments. Employee dashboard filters authorized
records by the signed-in member ID. These are working presentations of existing
permissions, not invented department-level permissions or a new employee API.
Selecting a dashboard cannot broaden backend visibility; denied datasets remain
explicitly unavailable. Human users without employee task assignments see an
honest empty personal queue.

Canonical JS source is in packages/sdk and packages/ui. The Python console assets
are generated compatibility copies via `scripts/sync_console_adapters.py`;
Section 6 CI prohibits drift, browser persistence and iframe embedding. Section 4
explicitly permits the reviewed web/UI-to-SDK package edges. Existing console
unit/live-browser acceptance remains mandatory.

## Security headers and export packaging

Exported public HTML contains only sign-in markup and static Next runtime data.
Build-time SHA-256 hashes authorize the exact inline bootstrap scripts emitted by
Next. CSP script-src allows self and those reviewed static hashes, never inline
arbitrary JavaScript or eval. connect-src self, frame-ancestors none, nosniff,
DENY, no-referrer and private/no-store apply to frontend paths and assets.
Style-src permits inline style attributes used by reviewed meter renderers;
this does not permit inline script. Original `/console/` keeps its existing
strict CSP. Runtime paths use Starlette StaticFiles path containment, validated
by encoded traversal and unknown-route tests. No user-writable HTML is hosted.

## Verification and operation

Run from repository root:

```sh
npm ci
npm test
npm run build
python scripts/package_frontend.py
python scripts/check_frontend_architecture.py
python scripts/sync_console_adapters.py --check
python scripts/smoke_workspace_exports.py
```

Start the existing backend with its ordinary operator quickstart; open
`http://127.0.0.1:8000/workspace/`. Docker packages the frontend automatically.
The dev-only Next server is for component development; authenticated acceptance
runs against the packaged same-origin application, not cross-origin fetches.
Before Python-only source testing, build/package the export as above. Generated
output is ignored by git and rebuilt from the pinned lockfile for every release.

Browser acceptance has six Chromium/Firefox/WebKit desktop/phone/tablet projects,
WCAG 2.1 A/AA axe scans, real keyboard dialog interaction, direct URLs, expired
sessions, role denial, XSS strings, no token persistence and route responsiveness.
Fixtures validate UI contracts; separate live Chromium tests use real PostgreSQL
and signed sessions, persisted goals, restricted reviewer, mobile dashboards and
a complete two-human plan approval, task approval, execution and independent QA.
Physical Windows/mobile UAT and expert assistive-technology audit are not claimed.

Rollback reverts this section as one unit and rebuilds the prior image. No SQL
migration/rollback is needed. The established `/console/` stays available as a
compatible operational interface; never revert authorization/governance to work
around a frontend error. Acceptance details live in SECTION06_FINAL_ACCEPTANCE.md.
