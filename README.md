# AGO — Artificial General Organization

AGO is a **governed, multi-tenant AI-native organizational operating system**, currently implemented as a modular Python/FastAPI backend, PostgreSQL and a first-party web console. Its milestone foundations M1–M12 are present; **this is not a production-ready autonomous organization**.

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
- **M11 — Pilot Browser Acceptance:** real Chromium against live FastAPI/PostgreSQL, founder/reviewer workflow and mobile navigation, corrected approval-driven strategy activation, least-privilege independent QA queue, evidence screenshots and guarded logouts.
- **M12 — Local Founder Onboarding:** read-only redacted environment/schema doctor, existing tenant UUID listing, atomic local founder + independent reviewer provisioning, loopback-only one-command launch and safe Windows PowerShell operator helper. No destructive automatic migrations or password storage.

**BDR delivery policy:** [Complete one architecture section per batch with
all tests and evidence before starting another](docs/BDR_SECTION_DELIVERY_RULE.md).
A section blocked on external human/cloud settings is never mislabeled
fully accepted.

## Architecture section 1 — Overall System Architecture

All seven supplied Section 1 checklist gates are CI-accepted (278 Python
tests per matrix version, 14 JS, six Chromium, Docker and restore).
Section 1 now has a source-linked layer/context catalog, complete module
inventory, synchronous/asynchronous contracts, governed lifecycle, tenancy,
fault and scaling boundaries, and a read-only CI traceability gate.
See [Section 1 architecture](docs/architecture/SECTION_01_OVERALL_SYSTEM_ARCHITECTURE.md)
and [Section 1 acceptance evidence](docs/reports/SECTION01_FINAL_ACCEPTANCE.md).
Original full-blueprint parity remains unverified; other sections retain their
independent status.

## Architecture section 2 — High-Level Component Diagram

All seven supplied Section 2 checklist gates are CI-accepted: 288 Python
tests per matrix version, 14 JS, six Chromium, Docker and restore passed.
Six source-linked Mermaid views cover leadership, organization, orchestration,
knowledge/communication, execution/evidence and infrastructure/security. Current
and proposed relationships are explicitly distinguished. CI validates source
symbols, diagram drift, Mermaid syntax and a real brain-to-agent-to-QA workflow.
Read [Section 2 component architecture](docs/architecture/SECTION_02_HIGH_LEVEL_COMPONENT_DIAGRAM.md),
[all six component views](docs/architecture/SECTION_02_COMPONENT_VIEWS.md) and
[acceptance evidence](docs/reports/SECTION02_FINAL_ACCEPTANCE.md).
No missing subsystem is marked implemented because it appears in a diagram.

## Architecture section 3 — Domain-Driven Design

Nine context contracts describe aggregates, repositories, services, invariants,
published languages and consistency. CI checks complete module ownership and
reviewed SQL-access boundaries in addition to Section 14 imports.
Read [Section 3 contracts](docs/architecture/SECTION_03_DOMAIN_DRIVEN_DESIGN.md)
and [acceptance evidence](docs/reports/SECTION03_FINAL_ACCEPTANCE.md).

## Architecture section 4 — Monorepo and application shells

The existing backend is preserved alongside Next.js web/admin/docs shells,
a canonical API wrapper, seven machine-checked service boundaries and private
UI/SDK/shared packages. Root `npm ci`, `npm test`, `npm run build` and
`npm run dev:web` operate the new shells; existing Python/console commands
remain valid without npm. See [Section 4 architecture](docs/architecture/SECTION_04_MONOREPO_ARCHITECTURE.md)
and [acceptance evidence](docs/reports/SECTION04_FINAL_ACCEPTANCE.md).
This scaffold does not claim full frontend parity or separately deployed services.

## Architecture section 5 — Backend architecture

FastAPI adapters consume typed ports from one request-local repository scope.
Application services orchestrate transactions through context-owned repositories;
pure domain values have no database/framework dependencies. Strict inputs reject
unknown authority fields and coerced booleans; business errors preserve HTTP
status/detail with safe correlation metadata. See
[Section 5 contracts](docs/architecture/SECTION_05_BACKEND_ARCHITECTURE.md) and
[acceptance evidence](docs/reports/SECTION05_FINAL_ACCEPTANCE.md).
Run `python scripts/check_backend_architecture.py` for the source guard.

## Architecture section 6 — Next.js workspace

Eight Next.js routes now use AGO's signed-session APIs at `/workspace/`, with
executive, department and employee dashboards, shared React components and
canonical governed workflow adapters. The existing nonroot backend image serves
the static export on its own API origin. Tokens stay in tab memory; reload signs
out. Build locally with `npm ci`, `npm run build` and
`python scripts/package_frontend.py`, then use the existing backend quickstart.
See [frontend architecture](docs/architecture/SECTION_06_FRONTEND_ARCHITECTURE.md)
and [acceptance evidence](docs/reports/SECTION06_FINAL_ACCEPTANCE.md).

## Completed architecture section: 14 — Module Dependency Rules

The original 1–34 architecture checklist is tracked **separately** from
M1–M12 implementation milestones. **Section 14** now has an enforceable,
versioned architecture baseline: 76 owned root modules, 145 reviewed
existing internal import edges, a six-layer dependency matrix, cycle bans,
three protected approval/QA SQL ownership boundaries, a time-limited
exception process, service extraction/event contract specifications and
CI tests on Python 3.11/3.12/3.14.

```powershell
cd apps\backend
python -m ago.architecture_guard check
```

Read the [Section 14 module contract](docs/architecture/SECTION_14_MODULE_DEPENDENCY_RULES.md)
and [verification report](docs/reports/SECTION14_FINAL_ACCEPTANCE.md).
Other enterprise architecture sections remain independently pending; an
approved architecture exception still requires separately configured GitHub
branch protection for real code-owner approval.

## Fast local start (Windows)

From `apps/backend` after setting your own **localhost** `AGO_POSTGRES_DSN` and applying any reviewed development migrations:

```powershell
python -m ago.local_ops doctor    # Read-only environment/schema check
python -m ago.local_ops tenants   # Find your existing organization login UUID
python -m ago.local_ops init      # ONLY for a brand-new organization, explicit consent
python -m ago.local_ops serve     # Open http://127.0.0.1:8000/console/
```

From repo root you can instead run `.\\scripts\\ago.ps1 doctor`, `tenants`, `init`, or `serve`. Session secrets are never written to files and paid model/external tools are not enabled automatically. Review the [full Windows quickstart](docs/reports/M12_LOCAL_QUICKSTART.md) before changing a database.

Read the [architecture gap register](docs/ARCHITECTURE_STATUS_AND_BACKLOG.md): the original 35-section blueprint is not fully implemented and M0 historical source parity is unverified. **M1–M12 accepted slices do not mean the full AGO research vision or public production is finished.**

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

M12: [254 Python + 14 JS + 6 real browser tests](docs/reports/M12_FINAL_ACCEPTANCE.md), [first-run Windows guide](docs/reports/M12_LOCAL_QUICKSTART.md) and [original blueprint gap register](docs/ARCHITECTURE_STATUS_AND_BACKLOG.md).

M11: [236 Python + 14 JS + 6 real browser tests](docs/reports/M11_FINAL_ACCEPTANCE.md) and [pilot operator guide](docs/reports/M11_PILOT_OPERATOR_GUIDE.md). Browser automation uses disposable PostgreSQL and never accesses production accounts.

M10: [software acceptance and external release blockers](docs/reports/M10_FINAL_ACCEPTANCE.md), [operator runbook](docs/reports/M10_RELEASE_RUNBOOK.md) and [non-root preview stack](deploy/docker/compose.preview.yml). The real production preflight requires `AGO_ENVIRONMENT=production`, configured TLS, non-default secrets and verified migrations: `python -m ago.release_ops check`. A successful CI build is not a public deployment authorization.

A fresh tenant must be provisioned by the **local operator** using `python -m ago.bootstrap`; an independent human reviewer must be provisioned using `python -m ago.provision`. See `docs/reports/M3_M5_OPERATOR_AND_ACCEPTANCE.md` for details.

## CI
The GitHub Actions workflow `.github/workflows/ago-backend-ci.yml` uses disposable PostgreSQL and validates migrations, Ruff, JavaScript syntax/Node 22 UI tests, the complete pytest suite on **Python 3.11 and 3.14**, a constrained Docker runtime smoke, a genuine isolated PostgreSQL dump/restore drill and a separate real Chromium pilot against live FastAPI/PostgreSQL. Do not use production DB credentials for tests.

## Governance and safety
Nothing invokes consequential external tools by default. High-impact work requires tenant-scoped human authorization; strategic plan consent never replaces per-task approval. Optional paid model use is disabled unless explicitly enabled and separately billed by the provider; AGO credit units are only an internal quota and **not actual currency**.

The organization architecture blueprint and BDR rules remain authoritative. Work proceeds on the single `develop` branch.
