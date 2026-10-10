# AGO M9 — Organizational Control Center operator guide

## Scope and security

The first working **web control center** for AGO is served by the existing
FastAPI backend, using its M1–M8 PostgreSQL, human approvals and policy
invariants. It is not an unrelated mockup or a new frontend backend.

- Entry: **`http://127.0.0.1:8000/console/`** (local development only).
- Static assets: `/console/assets/`. No external CDN/font/API service.
- All business data is requested from same-origin authenticated `/v1` API.
- Browser **access token is tab-memory only**. Reload requires re-login;
  sign-out revokes the current token on the server and then clears the tab.
- Console shell is public static code; ALL organization records and mutations
  still require verified signed sessions, active tenant membership and DB RBAC.
- Static CSP allows local scripts/styles/API only, disallows inline JS,
  framing, unauthorized form origins, camera, microphone and location.
- No production SaaS domain, cloud host, TLS, MFA, SOC2, security audit or
  rate-limit certification is asserted in this milestone.

## Console workspaces

| Workspace | Live existing AGO API | Safe interactive workflow |
|---|---|---|
| Overview | M5 scorecard, governed tasks, approvals, M7 brief | Navigate to role-permitted action |
| Strategy | M3 goals, plans and plan DAG | Create goals and plans, add steps, submit, activate, materialize |
| Governance | M2 approvals/tasks, QA reviews and M6 council | Independent approve/reject, atomic new task approval, guarded AI/tool execution, QA review, council vote/finalize |
| Organization | M2 departments and employees | Create departments and register AI employees |
| Knowledge | M6 verified/pending evidence | Propose evidence and independently review sources |
| Operations & Tools | M8 enrollments, rules, tool runs and approvals | Propose/reconcile/disable tools, draft automation rules, scan verified events, dispatch separately approved tools |
| Calendar | M6 attendee-scoped event store | Schedule internal event, optionally invite an employee, cancel and RSVP |
| Digital Twin | M7 DNA/snapshots/simulation/verification | Explicit evidence capture; adjust three *hypothetical* thresholds; simulate, verify digest and propose human-reviewed advice |

The Digital Twin is an **evidence-backed what-if analysis**, not an autonomous
three-dimensional organization replica or a predictive trained model. It never
writes live DNA when comparing sliders. Independently approved M7 policy
activation remains a separate backend process.

All 403/401 cases must be shown as restricted/session-expired, rather than
fictional zero metrics or an unauthorized action. A self-authored approval
should never show a usable self-approval button. Backend denial is final.

## Opening AGO locally AFTER a single founder-approved pull

Preconditions: Python 3.11+ installed, valid development PostgreSQL DSN in
`AGO_POSTGRES_DSN` and a unique `AGO_SESSION_SECRET` at least 32 bytes. The
founder's previously configured Windows Python 3.14 and PostgreSQL are
supported by the backend test environment, but the **new M9 browser UI must
still be locally visually accepted**.

```powershell
cd C:\Users\rudra\Projects\ago-
git switch develop
git pull --ff-only origin develop
cd apps\backend
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
python -m uvicorn ago.main:app --host 127.0.0.1 --port 8000
```

In a browser open `http://127.0.0.1:8000/console/`. Login with the **existing**
tenant UUID, founder/reviewer email and password. Do not paste passwords or
DSN into chat. A session expires after 15 minutes and logout revokes it.

No npm or frontend installation is required to **serve** the M9 UI. Optional
console source tests require Node 22+:

```powershell
node --test tests_web/*.test.mjs
```

If PowerShell does not expand the wildcard, run:
`node --test tests_web/console.test.mjs`. Node is used only for tests, not for
hosting the console.

## Existing organization permission upgrade

M9 introduces no automatic permission grants; it reads effective, live RBAC
through `GET /v1/console/me`. Existing M1–M5 tenants may not yet have the
M6–M8 grants. Authorized local operators may review and explicitly opt into
individual milestone permissions per tenant:

```powershell
python -m ago.m6_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m6_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
python -m ago.m7_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m7_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
python -m ago.m8_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m8_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
```

Apply only the permissions appropriate for the tenant's real governance policy,
with explicit authorization. Reviewer roles deliberately cannot originate
founder-controlled operations. Independent approval cannot be silently bypassed.

## Verification and non-claims

GitHub Actions verifies Python 3.11 and 3.14, PostgreSQL migrations, Ruff,
Node.js source syntax, browser-side pure-function security/unit tests and
signed-session HTTP integration including logout, cross-tenant records and
task approval/QA. This is **automated CI validation, not full manual browser
inspection or production penetration testing**.

M9 does **not** add: new database, unrestricted AI actions, third-party OAuth,
automatic live DNA mutation, client-side authorization authority, production
hosting, mobile app distribution, backups/restore or 24/7 operational support.
Those require separately accepted M10 release engineering.
