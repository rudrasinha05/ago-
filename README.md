# AGO — Artificial General Organization

AGO is a **governed, multi-tenant AI-native organizational operating system**, currently implemented as a modular Python/FastAPI backend, PostgreSQL and a first-party web console. Its milestone foundations M1–M10 are present; **this is not a production-ready autonomous organization**.

## Implemented software milestones
- **M1 — Enterprise platform foundation:** configuration, logging, DI, outbox/inbox events, identity/RBAC, plugins, scheduler, observability.
- **M2 — Governance:** human approval, tenant-scoped organization, controlled tasks, independent QA, memory, audit and authenticated API.
- **M3 — Company Brain:** hierarchical goals, strategic plans, DAG steps, human approval before activation, governed task creation and prerequisite QA.
- **M4 — Governed workforce:** AI employee runs attached to approved tasks, allowlisted handlers, persisted results and evidence; deterministic offline demonstration handler; optional opt-in bounded Responses API provider.
- **M5 — Analytics/economics:** virtual credit caps, idempotent usage ledger, tenant scorecard, deterministic scenario simulation, human-approved *proposals* for experiments (never applied automatically).
- **M6 — Organizational collaboration:** cross-department handoffs, privacy-scoped calendar and audit, evidence-based human-reviewed knowledge graph, executive council voting with quorum and a second human approval, operational analytics and explicit permission upgrades.
- **M7 — Meta Brain & Organizational DNA:** tenant-scoped immutable operating-threshold versions, independent human review, executive evidence/fitness snapshots, verifiable digests, deterministic advisory recommendations, what-if evaluation and least-privilege APIs.
- **M8 — Enterprise Tools & Department Automation:** independent human-reviewed read-only enterprise tool enrollment, single-use M2-approved execution, provenance-based departmental triggers, bounded optional HTTPS telemetry, immutable evidence and operator-controlled rollback/reconciliation.

**Completed backend work is not equivalent to self-improving AGI, autonomous consequential actions, hosted UI, live external tools, production security or release readiness.** The larger enterprise architecture remains in `docs/PROJECT_HANDOVER.md` and `docs/M3_M5_IMPLEMENTATION_SCOPE.md`.

- **M9 — Control Center & Digital Twin:** responsive same-origin console, secure tab-memory sessions, real governance/operations UI, role-based actions, evidence-backed what-if assessments and independently protected task workflows.
- **M10 — Release Engineering & Security Gates:** fail-closed production configuration, HTTPS/host/body boundaries, schema-integrity readiness, non-root read-only Docker image, SHA-256 logical backups and isolated PostgreSQL recovery drills. **Not authorized for public production without separately approved operational controls.**

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

Open the AGO Control Center at **`http://127.0.0.1:8000/console/`** after starting Uvicorn and signing in with an existing tenant UUID and credentials. No npm is needed to serve the web console. Optional JavaScript tests use `node --test tests_web/console.test.mjs` (Node 22+).

API documentation: `http://127.0.0.1:8000/docs`. The M3–M9 APIs are under `/v1/brain`, `/v1/agents`, `/v1/insights`, `/v1/operations`, `/v1/knowledge`, `/v1/council`, `/v1/meta`, `/v1/tools` and `/v1/console`.

CI acceptance: [M3–M5 evidence](docs/reports/M3_M5_FINAL_ACCEPTANCE.md). M6 CI evidence: [155-test acceptance](docs/reports/M6_FINAL_ACCEPTANCE.md). [M7 CI evidence: 175-test acceptance](docs/reports/M7_FINAL_ACCEPTANCE.md). [M8 CI evidence: 202-test acceptance](docs/reports/M8_FINAL_ACCEPTANCE.md). Operator setup: [M6 Guide](docs/reports/M6_OPERATOR_GUIDE.md), [M7 Guide](docs/reports/M7_OPERATOR_GUIDE.md) and [M8 Guide](docs/reports/M8_OPERATOR_GUIDE.md). M9: [212 Python + 13 JS test evidence](docs/reports/M9_FINAL_ACCEPTANCE.md) and [control center operator guide](docs/reports/M9_OPERATOR_GUIDE.md).

M10: [software acceptance and external release blockers](docs/reports/M10_FINAL_ACCEPTANCE.md), [operator runbook](docs/reports/M10_RELEASE_RUNBOOK.md) and [non-root preview stack](deploy/docker/compose.preview.yml). The real production preflight requires `AGO_ENVIRONMENT=production`, configured TLS, non-default secrets and verified migrations: `python -m ago.release_ops check`. A successful CI build is not a public deployment authorization.

A fresh tenant must be provisioned by the **local operator** using `python -m ago.bootstrap`; an independent human reviewer must be provisioned using `python -m ago.provision`. See `docs/reports/M3_M5_OPERATOR_AND_ACCEPTANCE.md` for details.

## CI
The GitHub Actions workflow `.github/workflows/ago-backend-ci.yml` uses disposable PostgreSQL and validates migrations, Ruff, JavaScript syntax/Node 22 UI tests, the complete pytest suite on **Python 3.11 and 3.14**, a constrained Docker runtime smoke and a genuine isolated PostgreSQL dump/restore drill. Do not use production DB credentials for tests.

## Governance and safety
Nothing invokes consequential external tools by default. High-impact work requires tenant-scoped human authorization; strategic plan consent never replaces per-task approval. Optional paid model use is disabled unless explicitly enabled and separately billed by the provider; AGO credit units are only an internal quota and **not actual currency**.

The organization architecture blueprint and BDR rules remain authoritative. Work proceeds on the single `develop` branch.
