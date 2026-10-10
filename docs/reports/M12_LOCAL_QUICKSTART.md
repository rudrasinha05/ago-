# AGO — Windows Local Run Guide (M12)

AGO is a **web application** with a modular Python/FastAPI backend and
PostgreSQL database. It is not an Android APK or a standalone Windows .exe.

M1–M11 implemented backend and browser pilot capabilities; M12 adds secure
local-only first-time setup. It is **not** a self-directed AI company or
production SaaS. All consequential work still requires independent human
approval and per-task QA. Paid AI/network features remain disabled by default.

## AGO components

- **Backend:** `apps/backend/ago/` — signed login, governance, goals,
  departments/employees, guarded AI runs, independent QA, knowledge, credits,
  internal calendar, deterministic snapshots and registered read-only tools.
- **Web frontend:** `apps/backend/ago/console/index.html` + `app.js`,
  `views.js`, `actions.js`, `styles.css`. Same-origin at
  `http://127.0.0.1:8000/console/`. Eight workspaces: Overview, Strategy,
  Governance, Organization, Knowledge, Operations & Tools, Calendar,
  Digital Twin. No separate Node/Vite frontend dev server needed.
- **Database:** current PostgreSQL and 18 ordered, checksum-verified migrations
  in `deploy/sql/` (001–018). The local setup never resets existing tables.
- **Operator CLI:** `apps/backend/ago/local_ops.py` and convenience
  `scripts/ago.ps1`; **no GUI public self-signup** or anonymous founder
  creation.

## Before starting

Required: Windows 11, Python 3.11+ (Python 3.14 supported by CI),
PostgreSQL running on `localhost`, `AGO_POSTGRES_DSN` set *in your terminal*
to your **own** development database, and the repo on `develop`.

**Do not paste PostgreSQL credentials or passwords into chat.** The terminal
environment from a previous PowerShell window does not automatically survive
opening a new one. If `AGO_POSTGRES_DSN` is missing, configure it locally
using your PostgreSQL account securely.

### One consolidated pull — only when the founder requests it

From your existing Windows repository:

```powershell
cd C:\Users\rudra\Projects\ago-
git status --short
git switch develop
git pull --ff-only origin develop
cd apps\backend
python -m pip install -e ".[dev,postgres]"
```

If `git status` reports untracked `ago_backend.egg-info/`, this is Python
build metadata; M12 adds `*.egg-info/` to `.gitignore`. Do **not** use
`git clean -fd` or delete any local source. If a pull cannot fast-forward,
stop and inspect the diff; never force-reset `develop`.

### Migration is explicit, never automatic

If the DB has earlier migrations only, **back it up appropriately first**.
Then only for your local development database:

```powershell
python -m ago.event_runtime migrate
python -m ago.local_ops doctor
```

A healthy doctor prints JSON including `"ready":true` and
`"migrations_applied":true`. It does **not** print DSN/passwords. It will
refuse a remote database, production/staging mode, changed SQL hashes,
missing schema or weak configured session secret. Missing dev signing secret
is okay: `serve` creates a strong key **in that process memory only**.

Alternatively from repo root the PowerShell convenience commands are:

```powershell
.\scripts\ago.ps1 doctor
.\scripts\ago.ps1 tenants
.\scripts\ago.ps1 serve
```

`migrate` via that script demands typing `MIGRATE`. Neither doctor nor
serve migrates automatically. If PowerShell script execution policy blocks
the helper, run the equivalent `python -m ago.local_ops ...` commands above.

## First run: existing organization or new organization

**Existing local tenant** (previously bootstrapped): from `apps/backend`:

```powershell
python -m ago.local_ops tenants
```

This lists up to 100 existing local organization names and UUIDs. Use the
correct UUID, existing founder email and password on the browser login page.
Do **not** run `init` for a tenant that already exists; it always creates a
new separate organization and does not migrate your old account.

**New empty local organization:** from `apps/backend`:

```powershell
python -m ago.local_ops init
```

The prompts ask for organizational name, your founder email/password and
the **other real human reviewer's** email/password, then exact `CREATE`
confirmation. Passwords use terminal hidden entry and are never printed or
saved by AGO. This CLI creates an organization + founder + independent
reviewer atomically; failure rolls all three back. Copy the displayed
`tenant_id` into your *private* operator records so you can log in.

If you do not have a second independent human reviewer yet, you may create
**only a founder** using `python -m ago.bootstrap --organization "..."`
`--email "..."` (password prompted) instead; however approvals cannot be
self-authorized and full governed workflow must wait for a real independent
reviewer. Do not use a second identity controlled by the founder to bypass
governance.

## Run AGO

From `apps/backend`:

```powershell
python -m ago.local_ops serve
```

or from repo root:

```powershell
.\scripts\ago.ps1 serve
```

It performs a read-only preflight and starts Uvicorn **only on
127.0.0.1:8000**. It prints the browser URL. No Python dependencies are
installed silently, no SQL migrations are applied, and no external
provider tools or paid models are automatically enabled.

Open:

- **Main console:** http://127.0.0.1:8000/console/
- **Liveness:** http://127.0.0.1:8000/health/live
- **Readiness:** http://127.0.0.1:8000/health/ready
- **Developer API docs (local only):** http://127.0.0.1:8000/docs

Login using your tenant UUID + email + password. Refresh logs out by
design—session tokens stay in the tab's memory only. Stop the server with
**Ctrl+C**. If you restart a server that used an ephemeral signing key,
existing sessions become invalid; sign in again.

If port 8000 is occupied, use `python -m ago.local_ops serve --port 8010`.

## Verify after pull (only on a disposable test database)

**Important:** `AGO_TEST_POSTGRES_DSN` must point to a dedicated, migrated
scratch/test database, not your live/local development tenant database.
The test suite inserts records and creates disposable tenants.

```powershell
python -m ruff check ago tests tests_browser
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```

Pure frontend JS tests require optional Node.js 22+:

```powershell
node --test tests_web/console.test.mjs
```

Browser pilot tests require the optional Playwright Python package and its
Chromium binary and create test tenants, so keep them on a disposable
database. They are already gated in GitHub Actions CI.

## What is not finished

The founder's existing Windows deployment and browser signoff are **not
yet observed in GitHub CI**. No cloud-hosted production site, mobile APK,
self-modifying AGI workforce, full connector marketplace, business financial
payments, public SSO/MFA or external provider certification is implemented
as an automatic M12 side effect. See the explicit open phase register
`docs/ARCHITECTURE_STATUS_AND_BACKLOG.md`. A successful local launch is a
development pilot, **not permission to expose port 8000 publicly**.
