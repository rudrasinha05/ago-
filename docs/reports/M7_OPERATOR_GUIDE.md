# AGO M7 — Meta Brain and Organizational DNA operator guide

## Backend purpose

M7 adds a **governed executive decision-support system**, not autonomous AGI.
It analyzes existing tenant-scoped M2–M6 records and generates transparent,
deterministic evidence-linked recommendations; it never runs consequential actions.

### M7 endpoints (signed session + server-side PostgreSQL RBAC)

- `GET /v1/meta/dna/active`: current human-approved operating thresholds, or frozen baseline.
- `POST /v1/meta/dna`: submit candidate operating DNA thresholds. Returns a unique
  `approval_id`, but does **not** activate the candidate.
- `POST /v1/meta/dna/{dna_id}/reconcile`: after **another active authorized human**
  decides the precise M2 approval, activate or record rejection; supersede the old
  active profile in one transaction.
- `GET /v1/meta/dna`: immutable per-tenant version history.
- `POST /v1/meta/snapshots`: record source metrics, bounded fitness, risk flags
  and a SHA-256 source-evidence digest.
- `GET /v1/meta/snapshots`, `/v1/meta/snapshots/{id}`:
  read snapshot evidence in causal capture order.
- `GET /v1/meta/snapshots/{id}/verify`: recompute the digest with the historical
  DNA (or frozen baseline) and report whether evidence is unchanged.
- `POST /v1/meta/simulate`: evaluate an alternative three-threshold profile
  against stored evidence without changing any organizational state.
- `POST /v1/meta/snapshots/{id}/recommendations`: idempotently create
  deterministic, evidence-linked advisory proposals requiring *new independent*
  M2 approvals; never execute them.
- `POST /v1/meta/recommendations/{id}/reconcile`: finalize approved/rejected
  advisory records after independent human decision.
- `GET /v1/meta/recommendations`, `/v1/meta/brief`: read governed outcomes
  and the latest executive snapshot without broadening permissions.

The existing `/v1/insights/scorecard` also includes counts of M7 DNA versions,
executive snapshots and Meta Brain recommendations.

### The intentionally limited organizational DNA

Only these three operating thresholds are accepted:

```json
{
  "qa_target_pct": 85,
  "backlog_limit": 5,
  "budget_alert_pct": 80
}
```

Values are validated, tenant-scoped, versioned, and immutable. Changing them
does **not** change the Constitution, eliminate approvals, grant roles, change
departments, edit code, or automatically spend money. A passing Meta Brain
recommendation is **advice only**. If a real operational experiment is desired,
an operator must explicitly create and separately approve the existing M5
experiment and any consequential M2 task.

### Executive score definition

For tenants with at least one completed task:

```
fitness = (QA pass percentage * 0.45)
        + (task completion percentage * 0.35)
        + ((100 - virtual credit utilization percentage) * 0.20)
```

If there are **no completed tasks**, the score is null and the risk list includes
`insufficient_data`—not 100/100. Additional flags are limited to
`qa_below_target`, `backlog_over_limit`, and `budget_alert`. Internal AGO
credits are **not** real currency; the score is a defined engineering indicator,
not an empirical guarantee of success.

### Operator setup for an EXISTING M1–M6 tenant

M7 migrations do not silently expand existing permissions. A local operator may
review and explicitly grant the narrow allowlists to the selected tenant:

```powershell
python -m ago.m7_permissions --tenant-id "<TENANT_UUID>" --role founder --confirm
python -m ago.m7_permissions --tenant-id "<TENANT_UUID>" --role reviewer --confirm
```

The founder can propose/observe/reconcile; the reviewer only sees the M7 report
and candidates, and uses their existing independent M2 `approval:decide` grant.
The founder cannot approve their own M7 proposals.

### Local verification only when the founder requests it

Use the existing `develop` branch and disposable PostgreSQL test database.
Never post credentials or DSNs in chat, scripts or repositories.

```powershell
cd C:\Users\rudra\Projects\ago-
git pull --ff-only origin develop
cd apps\backend
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q --basetemp="C:\ago-pytest-temp"
```

M7 adds ordered migrations `016`–`017`. These are already tested against
PostgreSQL 16 in isolated GitHub CI; the founder's Windows PostgreSQL 18.6
requires a separate, founder-initiated compatibility check.

### Boundaries

- No automatic worker employment, firing, self-modification, deployment,
  access expansion, external communications or payments.
- Frozen deterministic scoring, not an adaptive trained model or guaranteed
  business fitness score.
- Source integrity does not prove factual correctness.
- No production TLS, secrets vault, DB least privilege, failover, load testing,
  backup certification or external security audit as part of M7.
- Frontend, external enterprise integrations and production deployment remain
  future, separately gated deliverables.

The authoritative implementation scope is `docs/M7_SCOPE.md`. BDR still
requires a single consolidated local pull initiated by the founder.
