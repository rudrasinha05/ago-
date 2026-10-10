# AGO M9 — Control Center and Digital Twin Backend/UI Acceptance

**Status: M9 first-party web console implemented and automated-CI accepted.**
This is an application-level milestone, **not a production release or a
manual cross-browser visual certification**.

## Verified evidence, October 10, 2026

- Verified functional `develop` commit:
  `6a381b5501973609f4ad47d3612ab75f405956ac`
- Passing GitHub Actions run:
  https://github.com/rudrasinha05/ago-/actions/runs/38021442610
- Python 3.11: **212 passed, zero failed; one pre-existing Starlette warning**.
- Python 3.14: **212 passed, zero failed; one pre-existing warning**.
- First-party JavaScript on Node 22: **13 passed, zero failed** on both CI jobs.
- PostgreSQL 16: all existing migrations **001–018 apply successfully**.
  **M9 adds no new SQL migration or database.**
- Ruff and JS syntax validation: **both passed**.
- Both Python versions built the distribution wheel and verified `index.html`,
  `styles.css`, `app.js`, `core.js`, `views.js` and `actions.js`
  are packaged as importable first-party console assets.
- M1–M8 backend regressions remain green.

## Six accepted M9 gates

1. **Same-origin secure frontend:** `/console/` delivers a polished
   responsive dark-mode AGO interface and local static assets from the existing
   FastAPI package; strict CSP, no framing/third-party fetch, no-store response
   policy and no external UI dependencies.
2. **Signed-session entry and logout:** real tenant UUID/email/password through
   M2; tab-memory-only bearer; authenticated `/v1/console/me` reads effective
   roles/permissions from PostgreSQL; server-side token revocation on sign-out;
   401 clears browser access.
3. **Live executive and governance views:** tenant-scoped scorecard, goals,
   plans, governed tasks, approvals, independent QA, council motions, workforce,
   organizational departments. Atomic task approval requests and guarded
   AI/tool execution are operational controls; approvals remain independent.
4. **Evidence-backed Digital Twin:** active M7 DNA and recorded executive
   snapshots, three validated what-if sliders, explicit simulation,
   cryptographic evidence re-verification and separately human-approved Meta
   Brain recommendations. **No slider automatically applies policy.**
5. **Organizational workspaces:** reviewed/pending knowledge, tenant tool
   enrollments and automation, role-scoped people directory, 30-day calendar,
   private event visibility, employee invitation/RSVP and creator cancellation.
   Empty/403/expired conditions never fabricate healthy organizational data.
6. **Security, accessibility and CI:** script-independent CSP, keyboard
   navigation, dialog labels, focus-visible states, reduced-motion support,
   responsive layouts, escaped user/provider strings, real signed-token and
   cross-tenant PostgreSQL tests, role-limited UI actions, pure Node tests for
   client URLs/session expiration/DNA bounds and guarded action visibility.

## Confirmed negative scenarios

- Without bearer, all tenant business API endpoints remain unauthorized while
  the public static login shell is accessible.
- Reviewer role cannot acquire founder permissions or create strategy goals.
- Browser cannot place arbitrary external API requests via the controlled client.
- API access token is not persisted in local/session storage.
- Expired bearer clears the client's authenticated state; explicit signout
  revokes the exact server token.
- Founder cannot approve their own request. The UI hides self-review controls,
  while the server independently rejects self-approval.
- A proposed M2 task requires a separately approved action before AI execution;
  a completed task requires independent QA.
- Private events reveal invitation status only within the tenant visibility
  check; RSVP controls appear only for invited employees.
- Digital Twin missing outcomes yield N/A, not a misleading 100% score.
- Frontend text is HTML-escaped; CSP disallows inline script execution.

## Important acceptance boundaries

- **Manual Chrome/Edge/mobile screenshot and interaction QA on the founder's
  Windows machine has not yet happened.** Automated CI proves the shipped
  Python and JS contracts, but cannot substitute for browser visual sign-off.
- The founder's environment has locally verified M1–M8 as 202 passing tests.
  M9's new UI/assets/test bundle has **not been locally pulled or tested**.
- Static console has no external CDN dependency or npm runtime installation.
- There is no live 3D organizational simulator, user-generated model provider,
  self-modifying agent code, autonomous real-world execution, SaaS OAuth or
  third-party write connector added in M9.
- Frontend/API production TLS, backup/failover, admin onboarding, egress
  isolation, secrets, performance/load, external security audit and publication
  are separately gated M10 release tasks.

Operator guide: `docs/reports/M9_OPERATOR_GUIDE.md`. Authoritative frozen
scope: `docs/M9_SCOPE.md`. No intermediate pull requested; single
`develop` branch retained under BDR.
