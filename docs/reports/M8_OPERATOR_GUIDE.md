# AGO M8 — Operator runbook: governed tools and departmental automation

M8 adds a **bounded, audited backend integration layer** to the previously
verified AGO architecture. It is **not** general external automation or a
production deployment clearance.

## Implemented M8 API
All requests require signed sessions and tenant-scoped PostgreSQL RBAC:
- `GET /v1/tools/catalog`: static read-only allowlist.
- `POST /v1/tools/enrollments`: request enrollment with an exact M2
  approval action; separate authorized active human must approve.
- `POST /v1/tools/enrollments/{id}/reconcile`: activate/reject only after
  the associated M2 decision.
- `POST /v1/tools/enrollments/{id}/disable`: operator emergency stop.
- `GET /v1/tools/enrollments` and `/{id}/history`: tenant/audit view.
- `POST /v1/tools/automation/rules`: define a department/AI worker, a
  pre-enrolled tool and a verified source kind.
- `POST /v1/tools/automation/rules/{id}/fire`, `/automation/scan`:
  idempotently create **pending tasks**, never execute them.
- `GET /v1/tools/automation/rules` and `/automation/firings`:
  scoped monitoring.
- `POST /v1/tools/tasks/{id}/run`: server-registered tool handler executes
  exactly once after a *separate* per-task M2 human approval, under an
  authorized human operator and active tenant enrollment.
- `GET /v1/tools/runs`, `/runs/{id}/evidence`: immutable result/audit.
- `POST /v1/tools/runs/recover-stale`: operator-only manual reconciliation,
  records `uncertain` outcome; does not replay the tool or external request.
- Existing `/v1/insights/scorecard` now includes M8 operational counters.

## Exactly three trusted read-only tools

| Action | Behavior | Default |
|---|---|---|
| `tool:scorecard` | Tenant-only operational counts, budgets | Available after enrollment |
| `tool:knowledge_digest` | Tenant-only verified/pending knowledge counts | Available after enrollment |
| `tool:external_metrics` | Fixed HTTPS GET of numeric telemetry | **DISABLED** until operator opts in |

No shell, arbitrary URL, repository deployment, messaging, payment, destructive
work, third-party write operation, dynamically discovered handler or browser
automation is enabled. Provider outputs are untrusted and still need QA.

## Approvals are NOT interchangeable

1. Founder/operator requests tool enrollment, independent reviewer approves
   `tool:enroll:<enrollment-id>`; operator reconciles to active.
2. Operator creates a tool-specific M2 task approval for each task or the
   automation creates a pending approval.
3. Independent reviewer approves that exact task action.
4. An authorized human dispatches the allowlisted tool **once**; evidence and
   result are persisted and terminal failures do not silently retry.
5. Independent QA reviews delivered results. There is no auto-QA pass.

`qa_pass` automation scans only **original** finished tasks with independent
passing reviews; tool-automation output tasks cannot cause feedback loops.
`knowledge_verified` scans only independently reviewed institutional nodes.

## Operator-only external metrics (optional, not production certified)

External GET is disabled until *all* are true:

- `AGO_M8_EXTERNAL_ENABLED=true`
- `AGO_M8_METRICS_HOST`: an explicitly operator-configured FQDN, not a
  URL or IP literal, with HTTPS and **fixed `/v1/metrics` path**.
- `AGO_M8_METRICS_TOKEN`: secret (never print, share or commit).
- Tenant-scoped independent M2 tool enrollment AND per-task approval.

The adapter follows no redirects, has bounded timeout/response, returns
finite numeric fields only and performs GET rather than modifying operations.
It does **not** replace a production egress firewall, DNS-rebinding protection,
private network isolation, certificate/secret controls, or an integration audit.
CI does not perform any actual external HTTP request. Do not enable on a
production network until these additional infrastructure gates pass.

## Operator grant for an EXISTING tenant

M8 database migrations intentionally do not elevate existing accounts.
After inspecting the exact founder/reviewer permission grants and choosing a
trusted test tenant, the authorized local operator can run:

```powershell
python -m ago.m8_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m8_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
```

M6 and M7 privilege upgrades, if not previously applied, are also explicit;
review `python -m ago.m6_permissions` and
`python -m ago.m7_permissions`. Do not silently grant all privileges.

## ONE consolidated local sync when the founder requests

Prerequisite: existing, valid `AGO_POSTGRES_DSN`,
`AGO_TEST_POSTGRES_DSN` (separate disposable test DB) and
`AGO_SESSION_SECRET`. Never paste connection strings or secrets into chat.

```powershell
cd C:\Users\rudra\Projects\ago-
git switch develop
git pull --ff-only origin develop
cd apps\backend
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```

New M8 migration: `018_enterprise_tooling.sql`; local may also apply M6–M7
migrations `012`–`017`. GitHub CI uses PostgreSQL 16, not the founder's
Windows PostgreSQL 18. Local acceptance is an additional gate.

## Production exclusions
External business connectors, OAuth account links, live SaaS writes,
multi-tenant load/rate hardening, realistic latency, production secret vault,
SSRF-safe egress isolation, OpenTelemetry export, high-availability,
disaster recovery, red-team review, hosted GUI and release certification
remain outside M8. Later M9/M10 milestones must be separately verified.
