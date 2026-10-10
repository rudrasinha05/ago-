# Section 4 — Folder / Monorepo Architecture

## Frozen seven-gate scope

The current founder checklist requires a versioned backend, Next.js web, admin/
docs/other app shells, all seven planned service directories, UI/SDK/shared
contracts, infrastructure/test/script/CI directories and coupling prevention.
The original complete blueprint remains unavailable. Existing backend paths,
operator commands, schema and modular-monolith runtime are preserved.

| Boundary | Delivered ownership / entry point |
|---|---|
| apps/backend | Existing FastAPI package, runtime, SQL integration and browser tests |
| apps/api | Loopback API launcher forwarding to `ago.main:app`; no duplicate backend |
| apps/web | Next.js App Router web shell, localhost port 3000 |
| apps/admin | Next.js administration shell, localhost port 3001 |
| apps/docs | Next.js architecture/documentation shell, localhost port 3002 |
| packages/ui | Shared responsive accessible shell component and styles |
| packages/shared | Immutable capability metadata and typed health contract |
| packages/sdk | Typed origin-bound read-only health client, timeout/redirect/credential controls |
| services/company-brain | Goal/plan/advisory boundary mapped to actual existing modules |
| services/workflow-engine | Task/workflow/run boundary mapped to actual existing modules |
| services/memory | Memory semantics and existing MemoryStore boundary |
| services/knowledge-graph | Evidence-reviewed graph boundary |
| services/auth | Identity/session/RBAC/login boundary |
| services/notification | Existing event/handoff/calendar foundation; no external notifier claim |
| services/analytics | Scorecard/evidence/simulation boundary |
| infrastructure, docker, deployment, monitoring | Explicit canonical references to deploy/ and current platform; no duplicated state |
| tests, scripts, .github/workflows | Cross-workspace ownership, developer guards and actual CI |

Service folders contain machine-checked boundary contracts and extraction rules;
their implementations remain in `apps/backend/ago`. This is the agreed
monorepo structure, not seven unapproved independently deployed services.
Application shells compile and export runnable HTML. They do not pretend to be
a complete Next.js replacement for the existing authenticated Control Center;
that broader frontend work remains Section 6. The new SDK is a functional
health-client foundation, not the complete public SDK/API platform in Section 34.

## Package and dependency direction

Root npm workspaces list exactly the six applications/packages. The private
packages are versioned together at 0.1.0. Web/admin/docs may depend on UI/shared;
UI and SDK may depend on shared; shared may depend on no other AGO package.
No app may import another app or walk filesystem paths into a sibling package.
Backend module coupling remains governed by Sections 3 and 14.

`section04_monorepo.json` freezes the workspace roster, directory coverage,
service map and internal package permissions. `check_monorepo.py` verifies
package identities/declarations, actual import paths, service extraction status
and the committed lockfile. Negative tests inject app coupling, filesystem
escapes, new dependency grants and unapproved service deployment changes.

## Reproducible build and local operation

Next.js 16.4.0 and React/React DOM 19.3.0 were verified from the package registry
and pinned exactly. Root `package-lock.json` records resolved dependencies.
Node 22+ is the tested workspace baseline. App Router installation guidance:
https://nextjs.org/docs/app/getting-started/installation (checked 2026-10-10).
No remote fonts, paid providers or business APIs are used during shell builds.

From repo root: `npm ci`, `npm run check:boundaries`, `npm test`, `npm run build`.
Then `npm run dev:web`, `npm run dev:admin` or `npm run dev:docs` starts a
loopback shell. The existing Python install/run and Control Center instructions
remain valid and require no npm. `python apps/api/serve.py --port 8000` forwards
to the same existing application with proxy trust disabled.

The shells show honest foundation/shell status and link to the existing local
Control Center. They contain no private sessions, privileged admin operation,
SSO replacement or cross-origin token forwarding. SDK calls omit credentials,
refuse redirects, require HTTPS except loopback, and bound request timeouts.
Private mutation features and UI parity require their own later section gates.

## Tests, CI and rollback

CI runs monorepo boundaries with the full Python suite, then a separate Node 22
job installs the lockfile, checks SDK negative/security cases, builds all three
Next apps and verifies real exported homepages. A build/export is required:
creating folders or README files alone does not count as app-shell acceptance.
Prior Python, PostgreSQL, JS console, Chromium, Docker and restore gates remain.
Generated node_modules, .next and out artifacts are ignored, never committed.

No data migration, old-app deletion or production deployment is required.
Rollback removes only this scaffold/tooling and its CI gate; existing backend,
console, schema and Docker image remain. Acceptance evidence is recorded in
`docs/reports/SECTION04_FINAL_ACCEPTANCE.md` before Section 5 begins.
