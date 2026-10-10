# M6 — Collaboration & Knowledge Operator Guide

M6 is a **backend operational milestone** on the existing AGO modular-monolith
architecture; it does not confer authority to contact third parties, publish,
deploy, spend money, or change constitutional policies automatically.

## Modules and API

All routes require authenticated signed sessions plus PostgreSQL-backed RBAC:
- `/v1/operations/handoffs`: cross-department request, independent receiving
  human acknowledgement, accept/reject/complete and append-only history
- `/v1/operations/calendar`: private or tenant calendar records, invited
  employee responses, creator-only cancellation and immutable audit
- `/v1/knowledge/nodes`: evidence-cited proposals; only independently verified
  nodes appear in the standard read feed; reviewer-only pending queue;
  verified relationships cannot cross tenants
- `/v1/council/motions`: independent human ballots, minimum two voters,
  role checks and a **separate M2 approval** required for passing a motion
- `/v1/insights/scorecard`: M6 handoff, event, knowledge and council counters
  added to existing M5 tenant scorecard

A passed council motion is only an advisory governance record. It does not
authorize executable tasks or activate policies. M2 per-task approval remains
mandatory.

## Setup for NEW development tenants

Migrate PostgreSQL first. Set `AGO_POSTGRES_DSN` and a private unique
`AGO_SESSION_SECRET` (minimum 32 bytes). Then provision a fresh organization
with `python -m ago.bootstrap --organization "Example" --email founder@example.test`.
Use `POST /v1/sessions` for founder credentials.

Use `organization:manage` to create receiving departments. Provision distinct
human reviewers using the operator-only command:

```powershell
python -m ago.provision --tenant-id "<TENANT_UUID>" --department-id "<DEPT_UUID>" --email reviewer-one@example.test
python -m ago.provision --tenant-id "<TENANT_UUID>" --department-id "<OTHER_DEPT_UUID>" --email reviewer-two@example.test
```

Passwords are prompted, never passed on the command line. Council motions
require at least two OTHER active human voters with `council:vote`. Founder
cannot vote on their own motion; a separate M2 human approval is required.

## Existing M1–M5 tenants

M6 migrations **do not automatically elevate existing roles**. Authorized local
operators can grant the defined M6 permission allowlists *after review*:

```powershell
python -m ago.m6_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m6_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
```

This is optional and scoped to an explicitly selected tenant and role.
Do not use production owner/superuser credentials for the HTTP app.
Role propagation is intentionally not hidden inside database migrations.

## One consolidated local sync, only when founder requests

With existing `AGO_POSTGRES_DSN` and disposable `AGO_TEST_POSTGRES_DSN`
configured:

```powershell
cd C:\Users\rudra\Projects\ago-
git pull --ff-only origin develop
cd apps\backend
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```

Migration checksums are enforced and previously applied SQL files must never be
edited. No need to repeat intermediate pulls. A CI result on PostgreSQL 16
does not by itself prove local PostgreSQL 18.6 compatibility.

## Production exclusions

This backend milestone does not deliver a web GUI, a real-world organization
operating automatically, email/calendar-provider synchronization, live
third-party tools, LLM-made executive decisions, zero-trust deployment,
load certification, security audit, or a commercial release. Record review
only means a human evaluated evidence; it is not a guarantee the claim is true.
