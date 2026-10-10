# Section 6 — Frontend Architecture Acceptance

Frozen scope: all eight supplied Section 6 requirements, baseline `c04df79`.
Original complete blueprint remains unavailable. Status: implementation in progress.

- [ ] Preserve responsive eight-workspace console and governed operations.
- [ ] Ship a working Next.js App Router frontend, packaged on the API origin.
- [ ] Define router, tab-memory session and stale-request-safe data architecture.
- [ ] Supply shared React design components and canonical compatibility adapters.
- [ ] Provide executive, department and employee dashboards using authorized records.
- [ ] Preserve signed sessions, backend RBAC and independent approval interfaces.
- [ ] Pass live API Chromium acceptance for the Next.js frontend.
- [ ] Pass bounded Chromium/Firefox/WebKit, mobile/tablet, keyboard and axe checks.

No new backend service, database or migration. Static Next.js export is included
in the existing Python release image and served at `/workspace/`. The existing
`/console/` remains the rollback-compatible first-party interface. Compatibility
renderers/actions are shared source adapters, not an iframe or parallel API.
Release evidence and rollback instructions will be recorded after verification.

Local verification: all three optimized Next.js builds/served exports, all
Section 1–6/14 guards, wheel with 71 actual frontend files, Ruff, 14 console JS,
eight SDK tests, three frontend HTTP/CSP tests and eight Chromium desktop/phone
browser journeys passed. Axe found and verified fixes for selected-button hover
contrast and keyboard-focusable horizontal tables. Local WebKit lacks system
libraries and Firefox acceptance could not finish; CI installs browser system
dependencies and remains the authoritative full browser matrix gate.

Local full Python execution has the established readiness failure without a
PostgreSQL DSN, and 60 database-dependent skips. One source-copy test raced with
concurrent generated build output; it passed when rerun after the build completed.
Final full Python/real-PostgreSQL and release-image CI are required before closure.
