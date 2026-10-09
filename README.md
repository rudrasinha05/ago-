# AGO — Artificial General Organization

AGO is a **governed, multi-tenant AI-native organizational operating system**, currently implemented as a modular Python/FastAPI backend with PostgreSQL. Its milestone foundations M1–M5 are present; **this is not a production-ready autonomous organization**.

## Implemented backend milestones
- **M1 — Enterprise platform foundation:** configuration, logging, DI, outbox/inbox events, identity/RBAC, plugins, scheduler, observability.
- **M2 — Governance:** human approval, tenant-scoped organization, controlled tasks, independent QA, memory, audit and authenticated API.
- **M3 — Company Brain:** hierarchical goals, strategic plans, DAG steps, human approval before activation, governed task creation and prerequisite QA.
- **M4 — Governed workforce:** AI employee runs attached to approved tasks, allowlisted handlers, persisted results and evidence; deterministic offline demonstration handler; optional opt-in bounded Responses API provider.
- **M5 — Analytics/economics:** virtual credit caps, idempotent usage ledger, tenant scorecard, deterministic scenario simulation, human-approved *proposals* for experiments (never applied automatically).

**Completed backend work is not equivalent to self-improving AGI, autonomous consequential actions, hosted UI, live external tools, production security or release readiness.** The larger enterprise architecture remains in `docs/PROJECT_HANDOVER.md` and `docs/M3_M5_IMPLEMENTATION_SCOPE.md`.

## Developer quick start
Requires Python 3.11+ and PostgreSQL 15+:

```powershell
cd apps/backend
python -m pip install -e ".[dev,postgres]"
# Set AGO_POSTGRES_DSN to your OWN migrated dev database URL.
python -m ago.event_runtime migrate
python -m ruff check ago tests
python -m pytest -q
# Set AGO_SESSION_SECRET to a unique random 32+ byte string.
python -m uvicorn ago.main:app --reload
```

API documentation: `http://127.0.0.1:8000/docs`. The M3–M5 APIs are under `/v1/brain`, `/v1/agents`, and `/v1/insights`.

A fresh tenant must be provisioned by the **local operator** using `python -m ago.bootstrap`; an independent human reviewer must be provisioned using `python -m ago.provision`. See `docs/reports/M3_M5_OPERATOR_AND_ACCEPTANCE.md` for details.

## CI
The GitHub Actions workflow `.github/workflows/ago-backend-ci.yml` uses disposable PostgreSQL and validates migrations, Ruff and the complete pytest suite on **Python 3.11 and 3.14**. Do not use production DB credentials for tests.

## Governance and safety
Nothing invokes consequential external tools by default. High-impact work requires tenant-scoped human authorization; strategic plan consent never replaces per-task approval. Optional paid model use is disabled unless explicitly enabled and separately billed by the provider; AGO credit units are only an internal quota and **not actual currency**.

The organization architecture blueprint and BDR rules remain authoritative. Work proceeds on the single `develop` branch.
