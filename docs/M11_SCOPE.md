# AGO M11 — Pilot Browser Acceptance & Operational Usability (frozen)

M11 verifies and repairs the actual M9 Control Center as a safe, usable pilot.
M11 does **not** redefine the previously approved M1–M10 architecture and is
not public production authorization.

## Five frozen acceptance gates

1. **Automated real browser harness:** Chromium against live FastAPI, real
   PostgreSQL 16 and clean test tenants. Runs in CI with trace/screenshots
   on failures. Preserve M1–M10 Python/Node gates.
2. **Founder walkthrough:** real login, eight functional nav workspaces,
   goal creation/persistence, Digital Twin explicit snapshot/what-if,
   logout/revocation and re-login. No placeholder data counted as success.
3. **Independent reviewer:** second human identity shows authorization
   restrictions; real browser must not expose founder mutation controls.
   Backend remains sole enforcement authority.
4. **Viewport/accessibility:** desktop and phone-sized Chromium; navigation,
   dialogs, keyboard, focus, readable error states and no uncaught JS/browser
   errors. Fix defects found, add regression coverage.
5. **Pilot evidence:** GitHub dual-version backend/Node CI plus independent
   browser-job green, verifiable screen captures (CI artifacts, never auth
   tokens), failure diagnostics and a one-shot operator guide for later founder
   Windows acceptance.

No new tenant database, no extra external tool or paid model access, no
unilateral changing of M1–M10 approval rules, no auto-public deployment. A
CI browser pass is an isolated pilot rehearsal, not founder-device signoff,
security penetration testing, production hosted verification, or automatic
production release.

BDR: single `develop` branch, freeze scope before implementing, no
intermediate founder pull.
