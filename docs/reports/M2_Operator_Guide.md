# AGO M2 operator guide — pending CI acceptance

## Components added
- PostgreSQL migrations 004–006 for approval audit, organization, tasks and QA
- Session-authenticated organizational HTTP API under `/v1`
- Tenant permission checks from persistent identity/RBAC grants
- Human reviewer verification for approval decisions and QA
- Atomic task claim and approval verification; one approval per task
- Independent QA records and append-only database triggers
- Local-only bootstrap for a founder account

## Bootstrap after migrations
Run from `apps/backend` with `AGO_POSTGRES_DSN` set and a **fresh tenant target**.
```powershell
python -m ago.bootstrap --organization "Example Organization" --email "founder@example.com"
```
Password is securely prompted. The bootstrap prints a tenant UUID. It does not provision a second reviewer, so self-approval remains disallowed. A separate active human reviewer must exist, with the `approval:decide` permission and a human employee row matching their account id.

For the API, set `AGO_SESSION_SECRET` to a unique random secret of at least 32 bytes **outside source control**, then start `uvicorn ago.main:app`. Obtain a short-lived session via `POST /v1/sessions`.

## Important limits
- Do not expose login to an untrusted network without upstream rate limiting and HTTPS.
- API mutations are restricted by persistent RBAC, but operational execution adapters are not included; `/tasks/{id}/start` records a state transition, not actual external execution.
- Database owners can disable audit triggers; configure separate runtime DB user for tamper-resistance.
- No production release readiness claim. CI and local PostgreSQL acceptance must be recorded.
- Founder explicitly asked **not** to request local pull until the founder initiates it.
