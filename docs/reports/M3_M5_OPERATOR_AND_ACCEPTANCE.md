# AGO M3–M5 — operator guide and CI acceptance

## Backend milestone status

M3 Company Brain, M4 governed workforce and M5 analytics/economics/simulation **backend vertical slices have passed CI**. The larger AGO enterprise blueprint (0–35) is not fully implemented and the product is not certified production-ready.

**Verified CI evidence, 2026-10-09:** GitHub Actions run
https://github.com/rudrasinha05/ago-/actions/runs/37967692641

- Python 3.11: **139 passed, 0 failed, 0 skipped; 1 nonblocking Starlette deprecation warning**.
- Python 3.14: **139 passed, 0 failed, 0 skipped; 1 nonblocking warning**.
- PostgreSQL 16 in isolated CI; ordered migrations **001–010 applied**.
- Ruff checks passed on both Python versions.
- Test coverage includes real signed sessions, strategy DAG planning, independent reviewer approval, task authorization, AI run replay protection, independent QA, virtual-credit cap/idempotency, scenario risk and policy experiment review.

## ONE local pull / verification, when the founder chooses

Use PowerShell in the existing project, not a new repository. Never put the DB password in messages, documentation or commits.

```powershell
cd C:\Users\rudra\Projects\ago-
git pull --ff-only origin develop
cd apps\backend

# In this same session, set AGO_POSTGRES_DSN and AGO_TEST_POSTGRES_DSN
# to the existing disposable 'ago_test' database. Quote URLs with encoded passwords.
# Set these only if missing; do not overwrite known-good local variables.

python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```

Migration runner checksums all applied SQL files and applies only new files. **Never execute integration tests against production.** PostgreSQL 18 on the user's workstation has not yet been tested against the latest schema.

## Provision and test an organization

After migrations (and preferably with a separate development database), set a unique 32+ byte `AGO_SESSION_SECRET`. Bootstrap is a local privileged operation; it is not a public endpoint:

```powershell
python -m ago.bootstrap --organization "Example AGO" --email "founder@example.com"
# Save the printed tenant UUID, then create a different human reviewer:
python -m ago.provision --tenant-id "<UUID>" --email "reviewer@example.com"
python -m uvicorn ago.main:app --reload
```

Both commands securely prompt for distinct passwords. Use `POST /v1/sessions` with tenant UUID, email and password to receive a short-lived bearer token. Attach it to authenticated calls; `/docs` lists the routes.

**Typical controlled flow:** founder creates goal -> draft plan -> agent step -> submits plan -> independent reviewer approves `brain:activate:<plan-id>` -> founder activates/materializes -> founder requests each task approval -> reviewer approves -> authorized human dispatches the allowlisted task -> independent QA reviews result -> scorecard counts the result.

## Optional paid AI model integration

The default `internal:brief` is a deterministic safety/demo handler, **not a large language model**. To enable paid text model use for approved `research:brief` tasks, explicitly configure these values in a trusted development environment:

- `AGO_ENABLE_PAID_MODELS=true`
- `AGO_LLM_API_KEY` (secret; never commit)
- `AGO_LLM_MODEL` (a model available in your API account)
- A virtual-credit budget configured under `/v1/insights/budget`

The HTTP adapter uses the Responses API with storage disabled, bounded output, no tool calls and a fixed HTTPS endpoint. Each attempted `research:brief` uses **one virtual credit**; the provider may charge **real money separately**. Do not enable without reviewing its price/permissions. Offline CI mocks provider calls; it does **not** confirm live API connectivity or actual costs.

## Explicit acceptance exclusions
- Not a full GUI/frontend, deployed enterprise OS or self-evolving AGI.
- No built-in finance transfers, external messaging, deploy/delete or unrestricted agent tools.
- Model provider availability, real billing, operation recovery, load performance and failover unverified.
- Production prerequisites still include least-privilege DB roles, secret vault, TLS, upstream rate limits, backups, incident observability, threat modeling and external security audit.
- Evolution experiment approvals remain records only: **no automatic code/policy mutations**.
