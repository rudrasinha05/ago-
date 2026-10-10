# AGO M9 — Organizational Control Center & Digital Twin (frozen)

M9 builds a **real, responsive web interface** over the existing M1–M8 FastAPI/PostgreSQL modular monolith. Frozen scope (six acceptance gates):

1. **Same-origin secure console**: Serve the static control center at `/console/` with local, versioned CSS/JS only; no CDN, external analytics, third-party fonts, build-time secrets or extra database. Content Security Policy, no-store HTML, X-Frame-Options, Referrer-Policy. Works with Python package installs.
2. **Signed-session entry**: Tenant UUID/email/password against existing `POST /v1/sessions`. Bearer token kept **in tab memory only**; refresh deliberately requires re-login; user-initiated logout clears it. Never save passwords/tokens to localStorage, cookies or querystrings. An expired session clears the UI on 401.
3. **Executive dashboard + operations**: Live tenant-scoped scorecard, tasks, approvals, agents, goals/plans and tools with partial-access states. Allow safely governed human approve/reject with reason, create goals, and create plans. Server remains sole authorization authority.
4. **Digital twin**: Use recorded executive snapshot and M7's `POST /v1/meta/simulate` to compare current approved organizational DNA to user-edited, bounded alternatives. Clearly label **hypothetical, non-applying simulation**. Capture snapshot only via explicit user action; never auto-trigger expense-bearing or consequential actions.
5. **Organizational workspaces**: Live department/employee directory, reviewed knowledge and pending review, council and calendar, plus signed-session tool enrollment status. No fictional data/metrics, no duplicate business rules and no exposure of private event details on 403.
6. **Access, accessibility and acceptance**: Keyboard navigable responsive dark interface, meaningful no-data/error/403 states, explicit consent for mutations, safe text rendering (XSS), unit tests for JS behavior and signed-session HTTP/static security contract; GitHub matrix validates backend, static UI and JS tests on Python 3.11/3.14.

M9 is an **operational web console**, not a fully autonomous organizational digital twin. Digital Twin here is explicitly an evidence-backed **what-if scenario**, not a 3D simulation or autonomous prediction. No new schema, unsafe side effects, credential sharing, CORS wildcard, personal account inference, external SaaS binding, production secrets/deployment or changes to original M1–M8 governance. M10 release engineering remains separately gated.

BDR: one `develop` branch, no mid-project scope expansion, no intermediate founder pull; finalize only with dual-version CI proof.
