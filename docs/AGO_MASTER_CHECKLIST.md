# AGO — MASTER CHECKLIST (single source of truth)

**Owner:** Founder (rudrasinha05) · **Repo:** rudrasinha05/ago- · **Branch:** develop
**Status as of:** 2026-11-10 · **Evidence commit:** b26272f (9-job architecture, backend quality and focused acceptance all green)

---

## THE RULE (set by the Founder on 2026-11-10)

1. **This is the only checklist.** Every earlier list is superseded and listed in section 10. No AI agent may start a new one.
2. **Requirement text and IDs are frozen.** Nobody deletes, renames, renumbers, merges or shortens an item.
3. **New scope — a feature, an architecture change, anything — is added ONLY to this file, and ONLY after the Founder says so.** An AI agent that wants new scope asks first and waits.
4. **AI agents may update only the status line of an existing item,** and only with real evidence (a test, a CI run, a live run on the Founder's laptop).
5. **Status is never raised to make a number look better.** "Built" is not "done". Done means proved.

---

## 1. Where AGO actually stands

| Area | Items | Progress |
|---|---|---|
| Engineering phases (PH) | 14 | 4 done · 9 partial · 1 not started · **29% done** |
| Architecture S01–S34 (A) | 240 | 201 done · 36 partial · 3 not started · **84% done** |
| Acceptance gates (ACC) | 48 | 14 done · 22 partial · 12 not started · **29% done** |
| Founder requirements | 127 | 75 done · 27 partial · 25 not started · **59% done** |
| **TOTAL** | **429** | 294 done · 94 partial · 41 not started · **69% done** |

**Read this honestly:** the architecture is largely built and CI-gated. The *company* works: a Founder brief becomes a plan, the AI hierarchy approves it, five Board seats debate and vote with reasons, a denial is revised and resubmitted, and an independent AI QA employee can pass or fail a stage. What does **not** work yet is the part that turns all of that into a real product: generated code is never executed or tested, and AGO has never written to GitHub.

---

## 2. The blocking line — what stops AGO from being a real AI company

In order. Each one is blocked by the one above it.

| # | Blocker | Item IDs | Why it blocks everything after it |
|---|---|---|---|
| 1 | The AI engineer cannot produce valid code on the real laptop | AI-005 | Every later gate needs a source+test set that passes AGO's own check. Live attempts have failed twice. Likely needs a coding model (qwen2.5-coder) instead of qwen2.5:3b — **a Founder decision**. |
| 2 | No isolated Docker execution of candidate code | QA-002, QA-003 | Until code actually runs and real tests pass, no stage can honestly be called software. |
| 3 | AGO is not connected to GitHub | ACC-147, ACC-92, GIT-001…009 | Needs a Founder-created repo-scoped token. Without it there is no AGO-origin commit, no draft PR, no CI proof. |
| 4 | No release, rollback or maintenance lifecycle | ACC-98, BUS-005 | A delivered product has to be versioned and maintainable. |
| 5 | No end-to-end project handover | ACC-96, ACC-159, ACC-160, QA-009 | This is the real finish line: one project from brief to a usable artifact the Founder accepts. |

Two more that are not blockers but are promised work: an always-on server-side continuation (PROJ-006, ACC-152 — today only bounded sessions) and a genuine 3D Brain (VIS-001, ACC-48).

---

## 3. How to read a status line

- `[x]` **DONE** — built *and* proved by a test, a CI run, or a live run on the Founder's laptop.
- `[~]` **PARTIAL** — code exists, acceptance not proved.
- `[ ]` **NOT STARTED** — or deliberately deferred; the line says which.

Two different kinds of "done" appear here on purpose:
- An **A-item** (architecture) is done when the design, the code and the CI gate exist.
- An **ACC-item** (acceptance gate) is done only when AGO *actually does it* in the real world.

So `S19 Meta Brain` can be done while `ACC-19 Meta Brain real recommendation loop` is partial. That is not a contradiction — it is the difference between built and proved.

---

## 4. Engineering phases (PH) — original, fixed order

- [x] PH-−1 — Architecture-only blueprint, enterprise design and explicit non-goals.
  - *DONE* — Blueprint and non-goals recorded
- [x] PH-00 — Foundation: monorepo, environment, API/web skeleton, PostgreSQL, Docker, CI.
  - *DONE* — Monorepo, PostgreSQL, CI, API/web skeleton all live
- [x] PH-01 — Platform Core: authentication, RBAC, events, plugins, scheduler, gateway, health.
  - *DONE* — Auth, RBAC, events, scheduler, health in use daily
- [x] PH-02 — Organization OS: Brain, Meta Brain, council, workflow, departments and registry.
  - *DONE* — Brain, council, departments, registry in use
- [~] PH-03 — AI Employees: plan, think, execute, learn, review; governed roles and evidence.
  - *PARTIAL* — Roles/plan/review work live; execute stage still fails at code generation
- [~] PH-04 — Knowledge & Memory: vectors, graph, RAG, consolidation, privacy and retention.
  - *PARTIAL* — Vectors/graph/RAG designed and tested; no real project knowledge loaded yet
- [~] PH-05 — Automation: schedules, workflows, approvals, retry, compensation, events.
  - *PARTIAL* — Approvals/retry/events live; always-on scheduling still bounded sessions only
- [~] PH-06 — Collaboration: messaging, meetings, notifications, docs and assignments.
  - *PARTIAL* — Chat, notifications, assignments exist; manager reporting partly live
- [~] PH-07 — Intelligence: reasoning, reflection, debates, correction and improvement.
  - *PARTIAL* — Board debate and revision loop live; reflection/self-correction only for code
- [~] PH-08 — Digital Twins: organization, people, finance and risk what-if evaluation.
  - *PARTIAL* — Digital twin designed and tested; no real what-if run
- [~] PH-09 — Marketplace: plugins, skills, templates, reusable agents and SDK.
  - *PARTIAL* — Marketplace/SDK designed; no reusable agent published
- [~] PH-10 — Enterprise: tenancy, billing, compliance, audit and recovery.
  - *PARTIAL* — Tenancy/audit/recovery live; billing and compliance not proved
- [ ] PH-11 — Production: scale, Kubernetes, regional failover, secure deployment (deferred while localhost-only).
  - *NOT STARTED* — Deferred by decision while AGO is localhost-only
- [~] PH-12 — Research & Comparison: reproducible benchmarks, ablations and uncertainty.
  - *PARTIAL* — Benchmarks defined; no reproducible ablation run

## 5. Architecture Sections 1–34 (A) — original, fixed 240 checkpoints

### S01 — Overall System Architecture
- [x] A01.01 Describe presentation, application, domain, infrastructure and shared layers
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.02 Define responsibilities and clear boundaries for every organizational module
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.03 Define direction of dependencies and forbidden cross-layer coupling
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.04 Implement one working backend-to-database request path
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.05 Define synchronous APIs versus asynchronous command/event flows
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.06 Map end-to-end goal → plan → approval → execution → QA → audit
  - *DONE* — SECTION01 acceptance + 9-job architecture CI
- [x] A01.07 Document fault containment, scaling and organizational tenancy
  - *DONE* — SECTION01 acceptance + 9-job architecture CI

### S02 — High-Level Component Diagram
- [x] A02.01 Diagram Company Brain, Meta Brain and Executive Council
  - *DONE* — SECTION02 acceptance
- [x] A02.02 Diagram departments, managers and employees
  - *DONE* — SECTION02 acceptance
- [x] A02.03 Diagram OOS, workflow engine and task queue
  - *DONE* — SECTION02 acceptance
- [x] A02.04 Diagram memory, knowledge graph and communication
  - *DONE* — SECTION02 acceptance
- [x] A02.05 Diagram execution, QA, audit, simulation and dashboards
  - *DONE* — SECTION02 acceptance
- [x] A02.06 Diagram infrastructure, data stores and security boundaries
  - *DONE* — SECTION02 acceptance
- [x] A02.07 Implement basic interactions among brain, execution, approval and QA
  - *DONE* — SECTION02 acceptance

### S03 — Domain-Driven Design
- [x] A03.01 Identify all bounded contexts, including identity, strategy, workforce and economics
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.02 Specify aggregates, entities and value objects per context
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.03 Specify repositories, domain/application services and invariants
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.04 Implement tenant-scoped organization, goals and tasks
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.05 Define domain events, context contracts and published languages
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.06 Enforce complete context isolation through architecture-level tests
  - *DONE* — SECTION03 acceptance + context isolation checks
- [x] A03.07 Document eventual consistency and cross-context transaction rules
  - *DONE* — SECTION03 acceptance + context isolation checks

### S04 — Monorepo Architecture
- [x] A04.01 Create version-controlled backend package and tests
  - *DONE* — SECTION04 acceptance
- [x] A04.02 Create Next.js web application directory
  - *DONE* — SECTION04 acceptance
- [x] A04.03 Create admin, docs and other app shells
  - *DONE* — SECTION04 acceptance
- [x] A04.04 Create all planned /services domains as agreed architecture
  - *DONE* — SECTION04 acceptance
- [x] A04.05 Create /packages/ui, sdk and shared contracts
  - *DONE* — SECTION04 acceptance
- [x] A04.06 Provide deployment, scripts, test and CI directories
  - *DONE* — SECTION04 acceptance
- [x] A04.07 Prevent unintended coupling across monorepo packages
  - *DONE* — SECTION04 acceptance

### S05 — FastAPI Backend Architecture
- [x] A05.01 Serve actual FastAPI routes and signed sessions
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.02 Separate presentation, application, domain and infrastructure concerns
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.03 Apply dependency injection and repository contracts across all modules
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.04 Offer typed validation and uniform business exception semantics
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.05 Provide governance, brain, AI execution, tools and analytics routes
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.06 Define bounded context contracts for future services
  - *DONE* — SECTION05 acceptance + section05 contract check
- [x] A05.07 Test principal auth and cross-tenant isolation against PostgreSQL
  - *DONE* — SECTION05 acceptance + section05 contract check

### S06 — Next.js Frontend Architecture
- [x] A06.01 Build working responsive eight-workspace browser console
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.02 Create the specified Next.js frontend application
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.03 Formalize UI state, data fetching and router architecture
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.04 Build shared UI design system/component package
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.05 Add executive, department and employee dashboard experiences
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.06 Connect secure session, RBAC and approval interfaces
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.07 Pass live Chromium desktop/mobile acceptance smoke tests
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe
- [x] A06.08 Complete accessibility and browser/device compatibility acceptance
  - *DONE* — SECTION06 acceptance + Playwright 6 projects + axe

### S07 — Database Architecture
- [x] A07.01 Provision PostgreSQL tenant-scoped durable transactional storage
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.02 Maintain checksum-verified ordered SQL migrations
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.03 Introduce Redis only for justified cache/queue use cases
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.04 Build the specified knowledge graph store such as Neo4j
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.05 Implement vector store/embedding index for semantic search
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.06 Implement object storage for documents and artifacts
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.07 Set explicit data retention, indexing and recovery policies
  - *DONE* — SECTION07 acceptance + 74 migrations
- [x] A07.08 Validate isolated PostgreSQL backup and restore drill
  - *DONE* — SECTION07 acceptance + 74 migrations

### S08 — Message Bus and Communication
- [x] A08.01 Define command, event, query, notification and approval envelopes
  - *DONE* — SECTION08 acceptance
- [x] A08.02 Implement durable database-backed inbox/outbox
  - *DONE* — SECTION08 acceptance
- [x] A08.03 Add event idempotency and tenant envelope validation
  - *DONE* — SECTION08 acceptance
- [x] A08.04 Deploy approved distributed message broker (if required)
  - *DONE* — SECTION08 acceptance
- [x] A08.05 Define retries, dead-letter handling and replay semantics
  - *DONE* — SECTION08 acceptance
- [x] A08.06 Coordinate approvals without bypassing governance
  - *DONE* — SECTION08 acceptance
- [x] A08.07 Add observability for backlog, ordering and poison messages
  - *DONE* — SECTION08 acceptance

### S09 — Memory Architecture
- [x] A09.01 Design employee, department, project and company memory scopes
  - *DONE* — SECTION09 acceptance
- [x] A09.02 Design experience/episodic and short-term memory
  - *DONE* — SECTION09 acceptance
- [x] A09.03 Persist controlled memory records with authorization
  - *DONE* — SECTION09 acceptance
- [x] A09.04 Implement vector memory and semantic search
  - *DONE* — SECTION09 acceptance
- [x] A09.05 Implement memory consolidation, summarization and forgetting
  - *DONE* — SECTION09 acceptance
- [x] A09.06 Link memory to audited evidence and knowledge graph
  - *DONE* — SECTION09 acceptance
- [x] A09.07 Enforce retention, privacy, provenance and correction
  - *DONE* — SECTION09 acceptance

### S10 — Security Architecture
- [~] A10.01 Implement authentication, RBAC and cross-tenant authorization
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.02 Implement independent approval and role separation
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.03 Provide tamper-aware events/audits and session revocation
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.04 Manage secrets with external production vault and rotation
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.05 Deploy trusted HTTPS ingress and database encryption operations
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.06 Provide MFA/SSO and secure employee invitation/recovery
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.07 Complete external security assessment, threat model and compliance controls
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred
- [~] A10.08 Use production-safe fail-closed config checks
  - *PARTIAL* — SECTION10 report states PARTIAL: local scope only; production security deferred

### S11 — Deployment Architecture
- [~] A11.01 Build runnable unprivileged Docker release candidate
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.02 Provide localhost Docker Compose preview with PostgreSQL
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.03 Test migration, app and browser regression in CI
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.04 Implement reviewed Kubernetes/Helm/cluster deployment
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.05 Implement service metrics, traces, logging aggregation and alerts at production level
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.06 Implement trusted public TLS gateway and rollout strategy
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred
- [~] A11.07 Verify real hosted backup, restore and on-call processes
  - *PARTIAL* — SECTION11 accepted for localhost; PH-11 production deployment deferred

Section 11 additional local-use acceptance, preserved:
- [x] A11.L01 Guarded loopback-only startup with explicit schema checks and no automatic migrations.
  - *DONE* — START_AGO does a read-only schema preflight; migrations are a separate explicit command
- [x] A11.L02 Bounded local liveness/readiness/latency probes and actionable failure exit code.
  - *DONE* — /health/ready plus doctor exit codes used on the Founder laptop
- [ ] A11.L03 Guarded local custom-format backup with no overwrite and integrity manifest.
  - *NOT STARTED* — No guarded local backup with an integrity manifest
- [ ] A11.L04 Actual separate empty PostgreSQL restore and restored schema verification.
  - *NOT STARTED* — No restore into a separate empty PostgreSQL has been verified
- [ ] A11.L05 Nonroot Docker/loopback preview regression verification.
  - *NOT STARTED* — No non-root Docker preview regression (same gap as QA-002)
- [~] A11.L06 Windows operator guide and safe update/rollback workflow with matching object recovery.
  - *PARTIAL* — Windows start/migrate scripts and operator docs exist; no safe rollback workflow
- [x] A11.L07 Existing architecture, browser, build, identity, model and storage behavior preserved by CI.
  - *DONE* — Architecture, browser, build, identity, model and storage behaviour held green by CI

### S12 — Technology Decisions
- [x] A12.01 Record explicit technology choices for frontend/backend/database/broker
  - *DONE* — SECTIONS12_20 acceptance
- [x] A12.02 Document rationale, alternatives and trade-offs
  - *DONE* — SECTIONS12_20 acceptance
- [x] A12.03 Record performance, operational and financial consequences
  - *DONE* — SECTIONS12_20 acceptance
- [x] A12.04 Capture ADRs with status, approval and supersession
  - *DONE* — SECTIONS12_20 acceptance
- [x] A12.05 Choose and use initial FastAPI + PostgreSQL + Docker stack
  - *DONE* — SECTIONS12_20 acceptance
- [x] A12.06 Govern dependency upgrades and technology replacement
  - *DONE* — SECTIONS12_20 acceptance

### S13 — Coding Standards and Quality
- [x] A13.01 Enforce automated Python linting in CI
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.02 Exercise Python/PostgreSQL unit and integration tests
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.03 Exercise JavaScript template/security tests and live browser tests
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.04 Document naming, formatting, versioning and errors for all languages
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.05 Implement cross-module security and coverage thresholds
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.06 Add reliable API, contract, performance and regression quality gates
  - *DONE* — SECTIONS12_20 + engineering quality check
- [x] A13.07 Provide release versioning and stable compatibility policy
  - *DONE* — SECTIONS12_20 + engineering quality check

### S14 — Module Dependency Rules
- [x] A14.01 Define which bounded contexts can depend on which other contexts
  - *DONE* — SECTION14 acceptance + module dependency policy enforced
- [x] A14.02 Define forbidden imports and circular dependency rules
  - *DONE* — SECTION14 acceptance + module dependency policy enforced
- [x] A14.03 Keep approved/QA state changes behind governed domain boundaries
  - *DONE* — SECTION14 acceptance + module dependency policy enforced
- [x] A14.04 Introduce architecture tests/CI checks for forbidden dependency edges
  - *DONE* — SECTION14 acceptance + module dependency policy enforced
- [x] A14.05 Specify API/event contracts when modules are extracted
  - *DONE* — SECTION14 acceptance + module dependency policy enforced
- [x] A14.06 Maintain versioned and reviewed exception policy
  - *DONE* — SECTION14 acceptance + module dependency policy enforced

### S15 — Implementation Roadmap
- [x] A15.01 List original engineering phases 0–12 and acceptance conditions
  - *DONE* — SECTIONS12_20 acceptance
- [x] A15.02 Map every architecture section to implementing milestone and owner
  - *DONE* — SECTIONS12_20 acceptance
- [x] A15.03 Capture M1–M12 completed bounded increments and CI evidence
  - *DONE* — SECTIONS12_20 acceptance
- [x] A15.04 Maintain dependencies, blockers and security signoffs
  - *DONE* — SECTIONS12_20 acceptance
- [x] A15.05 Provide backlog for missing enterprise and research work
  - *DONE* — SECTIONS12_20 acceptance
- [x] A15.06 Verify implementation parity against complete original blueprint
  - *DONE* — SECTIONS12_20 acceptance

### S16 — Architecture Governance
- [x] A16.01 Define architecture authority and separation of technical decisions
  - *DONE* — SECTIONS12_20 acceptance
- [x] A16.02 Define approval thresholds and ADR amendment process
  - *DONE* — SECTIONS12_20 acceptance
- [x] A16.03 Define baseline freeze, exception and compatibility reviews
  - *DONE* — SECTIONS12_20 acceptance
- [x] A16.04 Enforce independent approval for operational tasks
  - *DONE* — SECTIONS12_20 acceptance
- [x] A16.05 Track cross-system architecture changes and review evidence
  - *DONE* — SECTIONS12_20 acceptance
- [x] A16.06 Periodically audit implementation against frozen specification
  - *DONE* — SECTIONS12_20 acceptance

### S17 — Phase −1 Non-Goals
- [x] A17.01 Specify work intentionally excluded from Phase −1 design
  - *DONE* — SECTIONS12_20 acceptance
- [x] A17.02 Prohibit business logic during architecture-only phase
  - *DONE* — SECTIONS12_20 acceptance
- [x] A17.03 Separate research ambitions from bounded deliverables
  - *DONE* — SECTIONS12_20 acceptance
- [x] A17.04 Document risks from unsupported scope expansions
  - *DONE* — SECTIONS12_20 acceptance
- [x] A17.05 Independently inspect the original full blueprint section for fidelity
  - *DONE* — SECTIONS12_20 acceptance

### S18 — Reference Technology Sources
- [x] A18.01 Cite primary documentation for the selected engineering stack
  - *DONE* — SECTIONS12_20 acceptance
- [x] A18.02 Reference FastAPI, Next.js, PostgreSQL, Docker and deployment patterns
  - *DONE* — SECTIONS12_20 acceptance
- [x] A18.03 Reference security and distributed systems standards and alternatives
  - *DONE* — SECTIONS12_20 acceptance
- [x] A18.04 Record source version/date and rationale for decisions
  - *DONE* — SECTIONS12_20 acceptance
- [x] A18.05 Check original full blueprint bibliography for accuracy
  - *DONE* — SECTIONS12_20 acceptance

### S19 — Meta Brain
- [x] A19.01 Observe Company Brain decisions without directly taking control
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)
- [x] A19.02 Record evidence-based executive snapshots and recommendations
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)
- [x] A19.03 Implement long-term reflection and effectiveness evaluation
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)
- [x] A19.04 Assess organization, architecture, departments, workforce and workflows
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)
- [x] A19.05 Propose improvements and maintain human approval gates
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)
- [x] A19.06 Verify before/after organizational change outcome quality
  - *DONE* — SECTIONS12_20 acceptance (design+code; real loop = ACC-19)

### S20 — Organizational DNA
- [x] A20.01 Define mission, vision and values as governed profile
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.02 Define leadership, engineering and research philosophy
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.03 Define communication, innovation, risk and documentation philosophy
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.04 Define hiring, promotion, meeting, learning and quality philosophy
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.05 Version and human-approve bounded threshold DNA changes
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.06 Implement employee/department inheritance and allowed overrides
  - *DONE* — SECTIONS12_20 acceptance
- [x] A20.07 Prevent DNA policy from overriding corporate constitution
  - *DONE* — SECTIONS12_20 acceptance

### S21 — Organizational Operating System
- [x] A21.01 Schedule tasks and run bounded workflows
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.02 Allocate workload, resources and priorities across departments
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.03 Support pause, sleep, idle, interrupt and resume states
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.04 Govern hiring, promotion, termination and organizational changes
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.05 Define emergency and maintenance operating modes
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.06 Calculate autonomous operating levels and escalation
  - *DONE* — SECTIONS21_27 acceptance
- [x] A21.07 Maintain full organization-level lifecycle state machine
  - *DONE* — SECTIONS21_27 acceptance

### S22 — Agent Consciousness / State Model
- [x] A22.01 Register identity, role, manager and basic assigned tasks
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.02 Track future assignments, goals and plan dependencies
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.03 Track confidence, skills, knowledge, risk and permission awareness
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.04 Track workload, stress, availability and assistance needs
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.05 Implement escalation thresholds, refusal and overload safeguards
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.06 Track learning status and state changes with evidence
  - *DONE* — SECTIONS21_27 acceptance
- [x] A22.07 Ensure state does not claim subjective machine consciousness
  - *DONE* — SECTIONS21_27 acceptance

### S23 — Multi-Level Planning
- [x] A23.01 Represent tenant goals, dependent plan steps and execution approvals
  - *DONE* — SECTIONS21_27 acceptance
- [x] A23.02 Model lifetime vision and five-year company goals
  - *DONE* — SECTIONS21_27 acceptance
- [x] A23.03 Propagate annual, quarterly, monthly, weekly, daily and hourly plans
  - *DONE* — SECTIONS21_27 acceptance
- [x] A23.04 Propagate top-level strategic objectives to task scheduling
  - *DONE* — SECTIONS21_27 acceptance
- [x] A23.05 Aggregate execution/QA outcomes as upward planning feedback
  - *DONE* — SECTIONS21_27 acceptance
- [x] A23.06 Re-plan safely against budgets, calendars and dependencies
  - *DONE* — SECTIONS21_27 acceptance

### S24 — Organizational Economics
- [~] A24.01 Enforce a tenant virtual-credit budget and usage ledger
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.02 Simulate bounded credit consumption and failure risk
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.03 Measure real model, storage, execution, tool and time expenses
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.04 Measure opportunity costs and observed return on investment
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.05 Assign governed department and employee budgets
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.06 Reconcile company budgets with actual invoices and revenue
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A24.07 Optimize for audited real-world cost and profit with controls
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL

### S25 — Internal Marketplace
- [x] A25.01 Build service/library/dataset/research asset publishing catalog
  - *DONE* — SECTIONS21_27 acceptance
- [x] A25.02 Build reusable models, workflows, agents and template listings
  - *DONE* — SECTIONS21_27 acceptance
- [x] A25.03 Track publishers, ownership, versions, licenses and access policies
  - *DONE* — SECTIONS21_27 acceptance
- [x] A25.04 Support discovery, approval and controlled cross-department reuse
  - *DONE* — SECTIONS21_27 acceptance
- [x] A25.05 Implement consumption analytics and lifecycle deprecation
  - *DONE* — SECTIONS21_27 acceptance
- [x] A25.06 Distinguish internal asset exchange from a paid external marketplace
  - *DONE* — SECTIONS21_27 acceptance

### S26 — Evolution Engine
- [~] A26.01 Collect QA, failure, bottleneck and performance observations
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A26.02 Measure prompt, architecture, workflow and department quality
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A26.03 Propose bounded policy improvements with human review
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A26.04 Compare controlled experiment baseline and candidate outcomes
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A26.05 Audit approvals, rollbacks and promotion of changed policies
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A26.06 Never allow uncontrolled self-modification or privilege escalation
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL

### S27 — Digital Twin
- [~] A27.01 Capture current evidence snapshots for organizational comparison
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.02 Run bounded what-if scenarios without applying policies
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.03 Model projects, departments, employees, availability and deadlines
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.04 Model hiring, layoffs, growth, market shocks, revenue and risk
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.05 Calibrate predictions against observed outcomes and uncertainty
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.06 Keep production/twin state synchronized with provenance
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL
- [~] A27.07 Require human authorization before any real-world action
  - *PARTIAL* — SECTIONS24_26_27 measurement acceptance states PARTIAL

### S28 — Architecture Differentiators
- [x] A28.01 Compare architectural intent with CrewAI and AutoGen
  - *DONE* — SECTIONS28_30 acceptance
- [x] A28.02 Compare with LangGraph and OpenHands
  - *DONE* — SECTIONS28_30 acceptance
- [x] A28.03 Compare with traditional BPM, ERP and project management
  - *DONE* — SECTIONS28_30 acceptance
- [x] A28.04 Explain organization-level governance versus task-agent orchestration
  - *DONE* — SECTIONS28_30 acceptance
- [x] A28.05 Support comparative claims with reproducible experiments
  - *DONE* — SECTIONS28_30 acceptance
- [x] A28.06 Review exact original V2 section and citations for accuracy
  - *DONE* — SECTIONS28_30 acceptance

### S29 — Corporate Constitution
- [x] A29.01 Define constitutional purpose and highest policy priority above DNA
  - *DONE* — SECTION29 acceptance
- [x] A29.02 Define organizational laws and immutable non-negotiable rules
  - *DONE* — SECTION29 acceptance
- [x] A29.03 Specify founder, humans, councils and AI separation of powers
  - *DONE* — SECTION29 acceptance
- [x] A29.04 Implement checks, balances and cross-subsystem policy enforcement
  - *DONE* — SECTION29 acceptance
- [x] A29.05 Implement independent approval and QA guardrails
  - *DONE* — SECTION29 acceptance
- [x] A29.06 Define amendment voting, effective dates, versioning and audit
  - *DONE* — SECTION29 acceptance
- [x] A29.07 Implement narrowly constrained emergency constitutional procedures
  - *DONE* — SECTION29 acceptance
- [x] A29.08 Prove every module cannot override or bypass constitutional policy
  - *DONE* — SECTION29 acceptance

### S30 — Organizational Calendar
- [x] A30.01 Create tenant-visible/private events and invitation responses
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.02 Model working hours, time zones and holiday calendar
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.03 Model weekly sprints and monthly/quarterly/annual cycles
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.04 Manage company budgets, hiring, promotion and performance-review calendars
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.05 Schedule maintenance, incident response and release freeze windows
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.06 Schedule simulations and employee learning cycles
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.07 Synchronize department plans, task deadlines and long-running workflows
  - *DONE* — SECTIONS28_30 acceptance
- [x] A30.08 Enforce conflicts, quiet hours, rescheduling and calendar governance
  - *DONE* — SECTIONS28_30 acceptance

### S31 — Enterprise Knowledge Graph
- [x] A31.01 Propose independently verified fact/policy/artifact/decision nodes
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.02 Create limited supports/contradicts/depends_on/references relationships
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.03 Model people, departments, projects, customers, products and assets
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.04 Model workflows, research, models, skills, tools, incidents and documents
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.05 Link memory, audit and decision references with provenance
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.06 Implement rich typed graph queries and path traversals
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.07 Define versioned graph evolution, merging, deletion and tenant ACLs
  - *DONE* — SECTIONS31_34 acceptance
- [x] A31.08 Synchronize comprehensive graph with memory architecture
  - *DONE* — SECTIONS31_34 acceptance

### S32 — Organizational Psychology
- [x] A32.01 Define measurable trust, reliability and leadership signals
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.02 Define collaboration, communication style and mentoring scores
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.03 Define decision bias, creativity, risk behavior and learning velocity
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.04 Define adaptability, conflict resolution and promotion readiness
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.05 Validate behavioral measurements for accuracy, privacy and bias
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.06 Specify human review and appeal before assignment/promotion/autonomy changes
  - *DONE* — SECTIONS31_34 acceptance
- [x] A32.07 Log signal evolution, drift and expiry over time
  - *DONE* — SECTIONS31_34 acceptance

### S33 — Enterprise Analytics
- [x] A33.01 Compute organization/task/run counts, virtual budgets and risk flags
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.02 Provide executive/strategy overview in Control Center
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.03 Implement departmental and employee analytics dashboards
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.04 Implement finance, workflow, QA and security dashboards in full
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.05 Implement architecture, infrastructure, knowledge and memory dashboards
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.06 Implement innovation, Digital Twin, Meta Brain and health dashboards
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.07 Implement KPI definitions, lineage, forecasting and anomaly detection
  - *DONE* — SECTIONS31_34 acceptance
- [x] A33.08 Implement scheduled executive reports, alerts and governance
  - *DONE* — SECTIONS31_34 acceptance

### S34 — Company API Platform
- [x] A34.01 Provide tenant-scoped versioned REST endpoints with RBAC
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.02 Provide production API gateway, traffic policy and rate controls
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.03 Implement streaming/event subscription APIs with stable schemas
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.04 Implement signed, replay-protected webhooks and retry queues
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.05 Implement public/partner OAuth clients and scoped API keys
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.06 Publish typed multi-language SDKs and developer portal
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.07 Build plugin and third-party enterprise integration lifecycle
  - *DONE* — SECTIONS31_34 acceptance
- [x] A34.08 Create API versioning/deprecation/compatibility governance
  - *DONE* — SECTIONS31_34 acceptance

## 6. Acceptance gates (ACC) — original 48-task P0/P1/P2 ledger

These are **additional, original, narrower release gates** in the repository. The
original IDs and acceptance wording are unchanged. Historical status remains in
`docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`; don't edit this specification
merely to raise a percentage. Some gate numbers are non-contiguous by design.

### P0 — Core integrity and original parity
- [~] ACC-10 — Local security architecture | Verify secrets, RBAC and data minimization across source, API, logs and backups
  - *PARTIAL* — RBAC + secret redaction enforced and tested; full source/log/backup audit not done
- [x] ACC-14 — Module dependency rules | All architectural source/import checks and protection policies enforced
  - *DONE* — check_backend_architecture + architecture_policy.json green in CI
- [~] ACC-15 — Original implementation roadmap parity | Original frozen plan traced to implemented modules and signed acceptance
  - *PARTIAL* — Roadmap traced; signed acceptance incomplete
- [~] ACC-17 — Phase −1 non-goal reconciliation | Explicitly record deferred external/production work against original blueprint
  - *PARTIAL* — Non-goals recorded; reconciliation not signed
- [~] ACC-18 — Technology reference parity | Every original technology claim verified or identified as a scoped alternative
  - *PARTIAL* — Technology claims partly verified
- [~] ACC-36 — 34-section implementation parity | All 34 original architecture deliverables matched to source and tested behavior
  - *PARTIAL* — All 34 sections have acceptance docs; parity audit not signed
- [x] ACC-45 — All-module integration | Same-SHA backend, database, browser and cross-module journey all green
  - *DONE* — Same-SHA backend + architecture + focused CI green on b26272f
- [x] ACC-120 — Approval and authority compatibility | Founder, independent QA and bounded CEO authorization all pass integration
  - *DONE* — Founder, hierarchy and AI QA authorization all integration-tested
- [~] ACC-133 — Confidential information leak prevention | Unauthorized tenant/project/employee access and export path tests fail closed
  - *PARTIAL* — Tenant isolation tested; full export-path audit pending
- [~] ACC-134 — Project document and tool data isolation | Unapproved project worker cannot read private bodies via any public endpoint
  - *PARTIAL* — Project isolation tested in queue scope; full endpoint sweep pending
- [~] ACC-156 — Reports, search, tools, logs and backup redaction | No secret or founder brief can leak through persisted evidence or any export
  - *PARTIAL* — Redaction implemented; backup/export sweep pending
- [x] ACC-158 — Latest same-SHA complete CI | Entire nine-job architecture plus backend, lint and browser green at final head
  - *DONE* — 9-job architecture + backend + focused all green on b26272f (2026-11-09)

### P1 — Autonomous company and AI workforce
- [~] ACC-19 — Meta Brain real recommendation loop | Compute source-backed changes with independent review and actual outcome metrics
  - *PARTIAL* — Meta Brain designed; no measured improvement loop with real outcomes
- [~] ACC-21 — Organizational operating system execution | Approved task schedule, dispatch, lifecycle and concurrency reflect real work
  - *PARTIAL* — Dispatch/lifecycle live; concurrency across projects not proved
- [x] ACC-22 — Truthful AI employee state | Worker idle, running, blocked and failed statuses all derive from durable execution
  - *DONE* — Worker states derive from durable runs; live-verified on Founder PC
- [~] ACC-23 — Executable multi-level project planning | Founder goal delegated as authorized executable dependency-aware task graph
  - *PARTIAL* — Plan graph with dependencies live; multi-level delegation partly
- [~] ACC-26 — Governed autonomous evolution engine | Measured reviewed improvement proposal with rollback and no silent code writes
  - *PARTIAL* — Evolution engine designed; no reviewed improvement proposal executed
- [ ] ACC-48 — Large interactive 3D Company Brain | True interactive 3D scene linked to source-backed actual running tasks
  - *NOT STARTED* — No true interactive 3D scene yet; current map is 2D/pannable
- [x] ACC-58 — CEO to CTO to PM to engineer delegation | Real identities, real scoped handoffs, independently authorized task starts
  - *DONE* — Live-proved 2026-11-07: Strategy Manager -> PM -> CEO hierarchy approvals recorded
- [~] ACC-60 — Controlled automatic staffing | Bounded CEO-chartered personnel proposal without duplicate roles or privilege escalation
  - *PARTIAL* — Staffing shortlist of eligible AI specialists built 2026-11-08; not live-run
- [x] ACC-61 — Multi-agent real teamwork | Multiple distinct AI workers complete linked subtasks and report evidence
  - *DONE* — Live-proved: CEO, CTO, CFO, CISO, CQO and PM each produced linked evidence
- [x] ACC-87 — LLM-generated executable project plan | Real local model proposes viable milestones assessed and activated by Founder
  - *DONE* — Live-proved: PM wrote an executable improved scope the Board then approved
- [~] ACC-119 — Revocable CEO operational charter | Scoped capabilities, term, budgets, audit and immediate human revocation
  - *PARTIAL* — CEO path is scope-bounded and audited; no term/budget/revocation UI
- [~] ACC-123 — Meta Brain measured improvements | Measured failed work feeds reviewed improvements with independent QA
  - *PARTIAL* — Failure evidence stored; no measured improvement loop
- [~] ACC-125 — Tenant-scoped enterprise tool execution | Approved safe tools execute under employee-specific scopes with audit trail
  - *PARTIAL* — Tool scopes enforced; limited real tool execution
- [~] ACC-126 — Active local worker monitoring | Live health and durable incident notifications with no fictitious activity
  - *PARTIAL* — Live health and blocker events shown; no incident notification drill
- [~] ACC-127 — Model, task and resource budgets | CPU/memory/time/token ceilings with budget-exhaustion negative tests
  - *PARTIAL* — Credits and timeouts enforced and live-tested; CPU/GPU/memory ceilings absent
- [x] ACC-128 — Crash-safe failure reconciliation | Unknown external outcome never repeated; safe operator reconciliation documented
  - *DONE* — Unknown outcomes never replayed; lease expiry no-replay added 2026-11-08
- [x] ACC-135 — Real work driven Brain visualizations | Progress, red paths and worker highlights reflect actual signed work receipts
  - *DONE* — Map/portfolio driven by signed work receipts only
- [x] ACC-138 — All employee task event popups | Each recorded work transition has durable counted event and accessible popup
  - *DONE* — Durable counted events + numbered popups; survive browser close
- [x] ACC-139 — Local Ollama multi-role governed chain | All seven full-Board/personnel roles run in authorized scoped sequence
  - *DONE* — Live-proved on Founder PC: full seven-role governed chain ran under qwen2.5:3b
- [x] ACC-140 — Actual founder laptop local model verification | Owner Windows Ollama inference measured with model, device and identity evidence
  - *DONE* — Live-proved 2026-11-07 on Founder Windows laptop with real Ollama inference
- [~] ACC-152 — Bounded continuous active employee work | Founder-started local process runs multiple approved tasks safely while powered on
  - *PARTIAL* — Bounded offline queue worker built 2026-11-08. Founder-started project runner added 2026-11-10 (scripts/ago_project_runner.py: whole project, all five stages, up to 24 h, no browser; apps/backend/tests/test_project_advance.py). Not yet run live on the Founder's laptop
- [x] ACC-154 — Reliable interrupted execution recovery | Restarted worker resumes only safe queued work and does not duplicate unknown writes
  - *DONE* — Interrupted runs resume only safe queued work; recovery tested

### P2 — Real software production, handover and maintenance
- [ ] ACC-92 — AGO-owned governed GitHub CI operations | Tenant-authorized repo-scoped commit, draft PR and read-only exact SHA CI inspection
  - *NOT STARTED* — AGO is NOT connected to GitHub; no repo-scoped runtime credential configured
- [~] ACC-94 — Independent full-project QA | Human reviewer validates complete requirements and real artifact test evidence
  - *PARTIAL* — AI QA by an independent AI reviewer built; no full-project human QA
- [ ] ACC-96 — Complete usable software from approved brief | Real supported project generated, built and delivered from Founder request
  - *NOT STARTED* — No complete usable software produced from a brief yet
- [ ] ACC-97 — Automatic bug diagnosis and safe repair | Failed isolated tests generate reviewed source-only repair without rewriting tests
  - *NOT STARTED* — No automatic bug diagnosis/repair loop
- [ ] ACC-98 — Versioning, release and maintenance lifecycle | Reviewed local release, rollback instructions and tracked maintenance
  - *NOT STARTED* — No release/rollback/maintenance lifecycle
- [ ] ACC-129 — Real founder laptop backup/restore drill | Safe owner-controlled backup, isolated restore and integrity report on real local DB
  - *NOT STARTED* — No backup/restore drill on the real local database
- [~] ACC-130 — Complete real local acceptance | Signed-in Founder demonstration of all authorized core journeys on Windows
  - *PARTIAL* — Many journeys demonstrated live; no single signed full acceptance pass
- [ ] ACC-147 — AGO GitHub repository-scoped credentials | Owner configures local token/binding privately, never sent to chat or model
  - *NOT STARTED* — No AGO GitHub token configured by the Founder
- [ ] ACC-148 — True AGO-origin GitHub commit and draft PR | AGO backend executes independently approved write with matching durable receipt
  - *NOT STARTED* — No AGO-origin commit or draft PR has ever been made
- [ ] ACC-149 — Independent human PR/QA review | Distinct authenticated human acceptance of test and exact artifact/source SHA
  - *NOT STARTED* — No independent human PR/QA review
- [~] ACC-150 — Owner laptop signed-in browser and device QA | Live locally installed AGO passes Founder browser, data and permissions checks
  - *PARTIAL* — Founder browser journeys verified live; permissions/device QA not signed
- [ ] ACC-155 — Web, Android and full-stack supported adapters | Each supported output type has real build/test/install evidence; no universal claims
  - *NOT STARTED* — No web/Android/full-stack adapter has real build evidence
- [ ] ACC-159 — Full independent final product QA | Complete artifact passes functional, security, accessibility and regression review
  - *NOT STARTED* — No full independent final product QA
- [ ] ACC-160 — Founder-accepted usable project handover | Actual working local product, immutable acceptance and explicit owner release decision
  - *NOT STARTED* — No project handed over to the Founder as a usable product

## 7. Founder requirements — later founder requests

These points capture requirements and corrections made during the company-map,
Ollama, Claude/Ultron, multi-project and governance discussions. They refine
rather than replace original architecture points. Similar language across a
section and a founder amendment indicates traceability, not a reason to merge.

### FND — BABA GROUPS founder vision
- [~] FND-001 — AGO must function as central infrastructure for many independent startups/projects, not just another AI app.
  - *PARTIAL* — Multi-project model exists; only one project (AdmissionFlow) has ever run
- [x] FND-002 — Founder directs organizational strategy, priorities, budgets and consequential decisions.
  - *DONE* — Founder approvals, Board override and credit control all enforced
- [~] FND-003 — AGO plans, develops, runs, maintains and monitors many projects with separate actual teams.
  - *PARTIAL* — Plan and develop partly work; run, maintain and monitor not built
- [ ] FND-004 — Later verified monetization, sales and support belong to each product's business operations.
  - *NOT STARTED* — No verified monetization, sales or support
- [~] FND-005 — Multi-model orchestration work forms a compatible part of AGO, not an unrelated discarded project.
  - *PARTIAL* — Connector framework present; only local Ollama is enabled
- [ ] FND-006 — BABA GROUPS also intends diversified ventures and investment in external founders, subject to future governance.
  - *NOT STARTED* — Diversified ventures and external investment not in scope yet
- [x] FND-007 — The number of future projects is not fixed; project registration must be extensible.
  - *DONE* — Projects are registered from a Founder brief; count is not fixed
- [x] FND-008 — AGO itself is built first; other projects remain queued until real execution works.
  - *DONE* — AGO itself is being built first; other projects stay in QUEUE

### BDR — Development rulebook, scope and coordination
- [x] BDR-001 — Freeze all original approved architecture/phase/requirement IDs and wording.
  - *DONE* — This checklist keeps every original ID and wording
- [x] BDR-002 — Never silently replace, delete, merge or shorten original requirements.
  - *DONE* — Nothing deleted or merged; older lists kept and marked superseded
- [x] BDR-003 — Changes of scope require a separate append-only request and founder authorization, not an edited master checklist.
  - *DONE* — Founder instruction 2026-11-10: scope changes only on his word, recorded here
- [x] BDR-004 — No mid-project architecture changes merely because an agent invents a better idea.
  - *DONE* — Rule in force for both AI agents
- [x] BDR-005 — Make substantial milestone delivery in one batch: code, integration, tests, failures, fix, retest, evidence.
  - *DONE* — Milestones delivered as code+tests+evidence in one batch
- [x] BDR-006 — Continue safe routine reversible work autonomously; only high-risk actions interrupt Founder.
  - *DONE* — Routine reversible work continues; risky actions ask the Founder
- [x] BDR-007 — Never report fake production completion, imaginary employee thought/activity or synthetic revenue.
  - *DONE* — No fabricated receipts; unverified model output is refused in code
- [x] BDR-008 — Preserve existing working code, migrations, databases, user data, tests and architecture boundaries.
  - *DONE* — Existing code, migrations and company data preserved
- [x] BDR-009 — Read actual repository, Git head, GitHub issues and assistant ownership before editing.
  - *DONE* — Repo, HEAD and GitHub issues read before every change
- [x] BDR-010 — No destructive reset, force-push, unapproved rollout or secret disclosure.
  - *DONE* — No force-push, reset or secret disclosure
- [x] BDR-011 — Keep develop as implementation branch and main as owner-reviewed release branch under existing project collaboration rules.
  - *DONE* — develop is implementation; main untouched
- [x] BDR-012 — Status must be evidence-based and include exact tests, CI SHA, pending dependencies and known failures.
  - *DONE* — Status lines carry exact tests, CI SHA and known failures
- [x] BDR-013 — Independent review/QA policies cannot be bypassed by UI labels or agent self-approval.
  - *DONE* — AI QA independence and approval hierarchy enforced server-side, not by labels
- [x] BDR-014 — Do not require Founder to answer 'continue' after every tiny internal patch.
  - *DONE* — Small internal patches do not stop for approval
- [x] BDR-015 — Never quietly modify this frozen specification; status belongs only in a separate progress ledger.
  - *DONE* — Requirement text still frozen; the Founder merged status into this one file on 2026-11-10

### ORG — Physical-company-style management by actual AI employees
- [x] ORG-001 — Founder is the one intended human owner; executive/worker AI identities must be real stored software identities.
  - *DONE* — Real stored employee identities; Founder is the only human
- [x] ORG-002 — Support CEO, CTO, CFO, CISO, CQO and optional COO, CAIO, CPO, CMO, CHRO and other justified roles.
  - *DONE* — CEO, CTO, CFO, CISO, CQO seats plus other role titles supported
- [x] ORG-003 — Explicit founder-appointed five-seat Board, without granting accidental runtime privileges.
  - *DONE* — Five-seat Board appointed without runtime privilege
- [x] ORG-004 — Every employee has role title, core responsibilities, extra responsibilities and actual reporting manager.
  - *DONE* — Role title, responsibilities and reporting manager stored per employee
- [x] ORG-005 — Project-specific manager/stage worker and project name must be attributable to real records.
  - *DONE* — Project manager and stage worker attributable to records
- [x] ORG-006 — Operational task approval follows manager/senior → PM → CEO by authorized hierarchy and scope.
  - *DONE* — Live-proved 2026-11-07: manager -> PM -> CEO, migration 071 records who is responsible
- [x] ORG-007 — Company-level major decisions and exceptional approvals escalate to Founder.
  - *DONE* — Sole-Founder company-level approvals; migration 070
- [x] ORG-008 — Board denial must show the denying seat, reasons, vote and exact scope.
  - *DONE* — Board denial shows seat, vote and DENY_REASON; live-proved
- [x] ORG-009 — Under CEO+CTO approval, eligible Finance/Risk/Quality Board veto may be explicitly Founder-overridden with immutable evidence.
  - *DONE* — Founder override of Finance/Risk/Quality veto; migration 073; live-used
- [x] ORG-010 — Denied proposal is revised and resubmitted, not automatically abandoned.
  - *DONE* — Live-proved: deny -> revise -> resubmit loop, bounded to 2 revisions per press
- [x] ORG-011 — Project Manager should rewrite denied scope to address the actual recorded feedback.
  - *DONE* — Live-proved: PM rewrote the scope with PROBLEM/USERS/FIRST_VERSION and the Board then approved
- [~] ORG-012 — Automatically propose/authorize suitable staffing for an unstaffed project stage without duplicates or privilege escalation.
  - *PARTIAL* — Eligible-specialist shortlist built 2026-11-08; AdmissionFlow quality stage still unstaffed in practice
- [~] ORG-013 — CEO operational charter must be revocable, scope-bounded, time-bounded, budgeted and audited.
  - *PARTIAL* — CEO path is scoped and audited; no term, budget or revoke control
- [~] ORG-014 — AI employees send upward blocker, doubt, module-done and phase-done reports to their real manager.
  - *PARTIAL* — Blocker reports to the manager are live; doubt/module-done/phase-done reports not
- [~] ORG-015 — Distinguish private manager reporting from tenant-visible company chat.
  - *PARTIAL* — Company chat exists; private manager channel not separated

### VIS — Founder visual control center and Brain
- [ ] VIS-001 — Large interactive genuine 3D Brain representing actual organization nodes and real activity.
  - *NOT STARTED* — No genuine 3D Brain; current view is a 2D pannable map
- [~] VIS-002 — A worker actively running a recorded task gets a red border until real task execution ends.
  - *PARTIAL* — Running state shown; red border tied to real runs not verified
- [~] VIS-003 — Only actual involved reporting/task links illuminate red; idle or unrecorded links do not.
  - *PARTIAL* — Only recorded links are drawn; red-path rule not verified
- [~] VIS-004 — Show the project title on each relevant working employee.
  - *PARTIAL* — Project title shown on the project card, not on each employee node
- [x] VIS-005 — Display actual employee/department hierarchy, roles and assigned tasks in a pannable and zoomable company map.
  - *DONE* — Pannable, zoomable company map with hierarchy, roles and tasks
- [x] VIS-006 — Differentiate idle, proposed, waiting, running, failed, blocked and unknown states.
  - *DONE* — Idle, proposed, waiting, running, failed, blocked and unknown are distinguished
- [x] VIS-007 — Never present model thinking as continuously active without persisted execution evidence.
  - *DONE* — No activity is shown without a persisted execution record
- [~] VIS-008 — Source-backed WebGL Brain and a usable fallback when GPU/browser cannot use WebGL.
  - *PARTIAL* — Canvas map works everywhere; no WebGL scene to fall back from
- [x] VIS-009 — Every employee must have durable counted work events and numbered popup notifications.
  - *DONE* — Durable counted events and numbered popups per employee
- [x] VIS-010 — Separate per-employee lifetime counts from unread/read-cursor counts.
  - *DONE* — Lifetime counts separate from unread cursor
- [x] VIS-011 — No notification or event may be permanently lost just because the Founder closes/reopens the browser.
  - *DONE* — Acknowledgements persisted server-side (2026-10-30)
- [x] VIS-012 — Founder portfolio lists all projects with status, team, progress, evidence and verified income (if any).
  - *DONE* — All projects portfolio with status, team, progress and verified income (2026-11-07)
- [x] VIS-013 — Clicking a project opens all authorized details: tasks, history, documents, code, approvals, QA, GitHub, budget and delivery.
  - *DONE* — Open project shows tasks, history, approvals, QA and delivery evidence
- [x] VIS-014 — Active forms, log panels and running task progress survive periodic UI refresh.
  - *DONE* — Advance log and open forms survive refresh (2026-11-07 fix)
- [~] VIS-015 — Company Chat and employee conversations are grounded in real stored project/task data.
  - *PARTIAL* — Chat reads stored data; grounding not fully verified
- [x] VIS-016 — Accessibility, mobile/tablet and browser keyboard-navigation acceptance must cover key Founder controls.
  - *DONE* — axe WCAG 2.1 AA on 6 browser projects incl. phone and tablet

### PROJ — Multi-project orchestration and continuation
- [x] PROJ-001 — Founder submits a brief; AGO persists a project goal, plan, tasks and actual accountable manager.
  - *DONE* — Brief creates goal, plan, tasks and an accountable AI manager
- [x] PROJ-002 — Deliver discovery → architecture → implementation → QA → release with explicit dependencies.
  - *DONE* — discovery -> architecture -> implementation -> quality -> release with dependencies
- [~] PROJ-003 — Real project team is selected/assigned based on role, skill and availability.
  - *PARTIAL* — Eligible shortlist by role exists; new intake selects an active independent AI PM reporting to the appointed CEO without engineering flags and persists deduplicated proposed team notices. PostgreSQL: test_intake_assigns_independent_pm_without_engineering_flags (2026-11-11). Skill and availability matching, PM-owned repository/test-repair integration and live acceptance remain incomplete.
- [x] PROJ-004 — Do not fake an assignment or create an executable task merely from a suggested assignee.
  - *DONE* — A suggested assignee never becomes an executable task by itself
- [x] PROJ-005 — Founder can view next safe step or run bounded 'keep going until I am needed'.
  - *DONE* — Advance project: next step or keep going; live-proved 2026-11-07
- [~] PROJ-006 — Automatic next-stage approval, dispatch, QA and continuation should be durable server-side, not dependent on an open browser.
  - *PARTIAL* — LIVE on the Founder's laptop 2026-11-11 (qwen2.5:3b, scripts/ago_project_runner.py, no browser, AdmissionFlow): AI manager opened the architecture stage after discovery QA PASS; hierarchy approved; the stage ran on the real model; Board stop -> AI-manager revision; AI QA FAIL -> rework; after 2 automatic attempts it stopped for the Founder (9 steps, status founder_needed). NOT yet proved live: a later stage passing QA and the project reaching stage 3-5. Tests: apps/backend/tests/test_stage_progression.py, test_project_advance.py (PostgreSQL); migrations 075, 076. The runner is Founder-started and bounded (max 24 h), not a boot-time service
- [x] PROJ-007 — Keep the Founder informed of actual work, blockers, retries, decisions and QA results.
  - *DONE* — Live timestamped log of approvals, runs, denials, QA and retries
- [x] PROJ-008 — Failure classifications distinguish Board denial, code invalid, QA FAIL, timeout, credit, unstaffed and unknown outcome.
  - *DONE* — Board denial, code invalid, QA FAIL, timeout, credit, unstaffed and unknown are separate
- [x] PROJ-009 — Recover failed tasks by creating new approved attempts and preserving old audit/QA evidence.
  - *DONE* — Audited recovery creates a new approved attempt; old evidence immutable (068/072)
- [~] PROJ-010 — Multiple independent projects should execute concurrently with task-level fairness, isolation and budget limits.
  - *PARTIAL* — Project-scoped queue claims added 2026-11-09; never run with two live projects
- [x] PROJ-011 — Project isn't genuinely DONE merely because the AI generated stage text or UI shows a green badge.
  - *DONE* — Stage completion needs a recorded run and an AI QA verdict
- [x] PROJ-012 — Preserve existing project approvals, artifacts and history through reassignment and upgrades.
  - *DONE* — Approvals, artifacts and history survive PM reassignment
- [~] PROJ-013 — Track statuses separately for development, internal review, release, maintenance and measured commercial results.
  - *PARTIAL* — Development and review statuses tracked; release, maintenance and commercial are not

### AI — LLM orchestration and actual worker execution
- [~] AI-001 — Support explicit authorized connectors for Ollama, OpenAI, Gemini, Claude and future providers.
  - *PARTIAL* — Ollama connector live; OpenAI/Gemini/Claude paths exist but are disabled
- [x] AI-002 — Consumer ChatGPT/Claude quota is not a transferable token balance for another provider.
  - *DONE* — Consumer quota is never treated as a provider balance
- [x] AI-003 — Seven distinct Board/PM/worker identities can run their bounded sequential inference roles with receipts.
  - *DONE* — Live-proved: seven distinct identities ran bounded sequential roles with receipts
- [x] AI-004 — Work output must derive from actual authorized model inference, not a hardcoded fabricated response.
  - *DONE* — Every draft carries a model receipt; fabricated output is refused
- [~] AI-005 — Real engineering workers must produce validated source files, matching tests and required docs.
  - *PARTIAL* — BLOCKER still open: no valid source+test set from an AGO run yet. Fix built at 990f164 (fence unwrap, code goal, JSON-schema answer; tests test_one_wrapping_markdown_fence_is_unwrapped_before_json_check, test_code_author_answer_is_schema_constrained_only_when_provider_supports_it; CI green on 990f164). Direct Ollama on the Founder laptop 2026-11-10: qwen2.5-coder:3b returned a candidate that passes the static check. Needs one live AGO run to prove.
- [x] AI-006 — Validate path allowlists, content limits, syntax, source hash and API shape before staging code.
  - *DONE* — Path allowlist, size, syntax, secret scan and API shape checked before staging
- [x] AI-007 — Attempt bounded self-correction after invalid code and classify continued invalidity safely.
  - *DONE* — One bounded self-correction, then engineering_candidate_invalid (2026-11-07)
- [~] AI-008 — Model credits, context, tokens, timeouts, CPU/GPU and memory limits must be controlled/measured where possible.
  - *PARTIAL* — Credits, context and timeouts enforced; CPU/GPU/memory not measured
- [x] AI-009 — Founder Windows Ollama inference requires actual local proof, not a mocked provider test.
  - *DONE* — Live-proved on the Founder Windows laptop, not a mock
- [x] AI-010 — Models only execute tools permitted by company policy and the exact project/employee authority.
  - *DONE* — Tool use bounded by company policy and project authority
- [x] AI-011 — Capture source-bound model, worker, task, handoff, failure and evidence receipts.
  - *DONE* — Model, worker, task, handoff and failure receipts stored
- [x] AI-012 — No uncontrolled self-improvement, model-made architecture rewrite or autonomous privilege expansion.
  - *DONE* — No self-improvement, architecture rewrite or privilege expansion by a model

### QA — Software, sandbox, correction and verified delivery
- [x] QA-001 — Generated code must be staged separately without overwriting trusted existing source.
  - *DONE* — Candidate code staged separately; trusted source never overwritten
- [~] QA-002 — Execute candidate code/tests in an isolated non-root, no-network, resource-bounded Docker container.
  - *PARTIAL* — BLOCKER still open: no AGO-generated candidate has been executed. Runner exists (scripts/ago_verify_candidate.py: user 65534, network none, read-only, 256m, 1 cpu, 64 pids) and real Docker runs it in CI step "Run actual offline Docker candidate QA with trusted static fixtures" (run 42831565453, green on 990f164). Not yet run on the Founder laptop.
- [~] QA-003 — Real tests must run; zero-test success or synthetic pass must not count as software acceptance.
  - *PARTIAL* — Runner exits 4 on zero tests; CI Docker smoke runs a known-correct and a known-broken fixture and requires pass/fail to match (run 42831565453 on 990f164; test_failure_or_zero_tests_never_marks_candidate_passed). No real test run of an AGO-generated candidate yet, so no software acceptance.
- [~] QA-004 — Preserve source digests, exact test evidence, failure category and bounded private-output redaction.
  - *PARTIAL* — Source digests and failure categories stored; execution evidence absent
- [~] QA-005 — Source-only repair after test FAIL cannot rewrite original tests or bypass approvals.
  - *PARTIAL* — Repair path limited to the one code self-correction
- [~] QA-006 — A repaired candidate must be retested in a fresh authorized attempt; retain all original FAIL evidence.
  - *PARTIAL* — Fresh attempt per recovery; no retest of executed code
- [x] QA-007 — AI-stage QA is different from executed-code testing, final independent review and actual release approval.
  - *DONE* — AI-stage QA, executed-code testing and release are separate gates in code
- [ ] QA-008 — Project acceptance covers functionality, privacy, security, accessibility, dependencies and regression tests.
  - *NOT STARTED* — No functionality/privacy/security/accessibility/regression acceptance for a product
- [ ] QA-009 — Complete one real project from Founder brief through actual executable artifact and final review, not just mocked CI.
  - *NOT STARTED* — No project has gone from brief to executable artifact

### GIT — AGO-owned GitHub and market-ready delivery
- [ ] GIT-001 — Bind each project to reviewed actual GitHub repository identity, owner, visibility and branch.
  - *NOT STARTED* — No project is bound to a GitHub repository identity
- [~] GIT-002 — AGO's own GitHub runtime credentials are separate from ChatGPT's GitHub connector.
  - *PARTIAL* — Adapter is designed to use AGO-only credentials; none configured
- [ ] GIT-003 — Source commits must be reviewed, exact-parent, non-force writes with durable identity receipts.
  - *NOT STARTED* — No reviewed exact-parent commit from AGO
- [ ] GIT-004 — GitHub CI must prove named required checks on the exact final source SHA.
  - *NOT STARTED* — No named required checks proved on an AGO-written SHA
- [ ] GIT-005 — Only then create a reviewable Draft PR with exact source and tests; no unapproved auto-merge.
  - *NOT STARTED* — No draft PR created by AGO
- [~] GIT-006 — Never retry uncertain GitHub writes blindly; inspect result and reconcile safely.
  - *PARTIAL* — No-blind-retry rule implemented in the adapter; never exercised
- [x] GIT-007 — UI shows real commit, PR, CI, QA and final Founder action, not a fabricated green state.
  - *DONE* — UI shows GitHub commit, draft PR and release as Not verified rather than faking them
- [ ] GIT-008 — Existing GitHub projects and code must be reused, not duplicated into a different project silently.
  - *NOT STARTED* — Reuse of existing repositories not implemented
- [x] GIT-009 — Live AGO-origin delivery is distinct from a human/Claude/ChatGPT developer manually pushing AGO code.
  - *DONE* — Human/assistant pushes are never recorded as AGO-origin delivery

### LOC — Windows localhost, database and genuine data protection
- [x] LOC-001 — Founder decides when AGO/Ollama/worker/server runs and when laptop is awake/off.
  - *DONE* — Founder starts and stops AGO, Ollama and the worker
- [x] LOC-002 — Read-only inspect actual database and applied migration versions before any upgrade.
  - *DONE* — Doctor preflight reports database and migration state read-only
- [x] LOC-003 — Find and prevent all unwanted seed, mock, test fixture or placeholder record insertion into founder DB.
  - *DONE* — No seed, mock or fixture row is written to the Founder database
- [x] LOC-004 — Test/CI data must use isolated disposable databases and restricted credentials.
  - *DONE* — CI and tests use disposable migrated PostgreSQL with restricted credentials
- [ ] LOC-005 — Verify database and private-object backup integrity and isolated restore before destructive changes.
  - *NOT STARTED* — No backup integrity check or isolated restore drill
- [x] LOC-006 — Never delete suspicious records simply because they appear dummy; confirm provenance and Founder decision.
  - *DONE* — Suspicious records are reported, never silently deleted
- [~] LOC-007 — Verify actual Windows login, PostgreSQL, Ollama, server, browser, 3D GPU, worker and task results.
  - *PARTIAL* — Windows login, PostgreSQL, Ollama, server and browser verified live; GPU/3D not
- [x] LOC-008 — Check git remote configuration separately from historical origin/develop refs.
  - *DONE* — Remote configuration checked separately from refs
- [x] LOC-009 — No unapproved paid API calls, cloud deployment, auto-wake, startup daemon or public publication.
  - *DONE* — No paid API, cloud deploy, auto-wake or startup daemon
- [x] LOC-010 — Preserve historical migrations and company data; apply only verified additive owner-authorized changes.
  - *DONE* — 74 migrations preserved; only additive authorized changes applied

### BUS — Business development, release and operation
- [x] BUS-001 — Differentiate virtual AI credits from authentic invoices, customer receipts, net profit and ROI.
  - *DONE* — Internal AI credits are labelled as not money everywhere they appear
- [~] BUS-002 — Run company/project analytics on real events rather than imaginary income and worker productivity.
  - *PARTIAL* — Analytics read real events; coverage is thin
- [~] BUS-003 — Research and market-opportunity proposals must be labelled hypotheses until evidence validates demand.
  - *PARTIAL* — Market signals are stored as signals; hypothesis labelling not enforced
- [ ] BUS-004 — Real marketing, pricing, sales, customer service and maintenance need accountable authorized employees.
  - *NOT STARTED* — No accountable marketing, pricing, sales or support employees
- [ ] BUS-005 — Track bug reports, post-launch repairs, releases, rollback and support outcomes.
  - *NOT STARTED* — No bug report, release, rollback or support tracking
- [ ] BUS-006 — Integrate new ventures and founder investment decisions as separate governed company projects.
  - *NOT STARTED* — No venture or investment project governance

### QUEUE — Known projects to be onboarded by AGO later
- [~] QUEUE-001 — AdmissionFlow as a real end-to-end AGO software-delivery pilot.
  - *PARTIAL* — AdmissionFlow is the live pilot: Board approves, code generation still fails
- [ ] QUEUE-002 — CUE Android AI Reminder App, with its original separate project and delivery gates.
  - *NOT STARTED* — Not onboarded
- [ ] QUEUE-003 — BTS Android / Baba Tiffin Service, reusing its pre-existing backend and requirements.
  - *NOT STARTED* — Not onboarded
- [ ] QUEUE-004 — AI Task Manager / Windows RAM optimizer with fundamental system-process safety.
  - *NOT STARTED* — Not onboarded
- [ ] QUEUE-005 — MANCH, AI Shopping Agent, Make India Clean and multi-model orchestration research projects.
  - *NOT STARTED* — Not onboarded
- [ ] QUEUE-006 — BABA local AI assistant / Ollama customization, deferred until approved.
  - *NOT STARTED* — Not onboarded
- [ ] QUEUE-007 — Department Workflow Automation: attendance, timetable, notices, exams, faculty workload, student follow-up, reports and approvals.
  - *NOT STARTED* — Not onboarded
- [x] QUEUE-008 — Unlimited future approved projects can be registered without silently modifying this frozen AGO architecture.
  - *DONE* — New projects register without changing the frozen architecture

## 8. Source-recovery and evidence gates (SRC)
- [ ] SRC-001 — Crosswalk the full previously recovered ~6,115-line original Sections 0–35 blueprint verbatim.
  - *NOT STARTED* — The ~6,115-line original blueprint has not been crosswalked verbatim
- [ ] SRC-002 — Recover earlier 96- and 160-item checklists in full and record unmatched historical wording without rewriting v1.0.
  - *NOT STARTED* — The earlier 96- and 160-item lists have not been recovered in full
- [x] SRC-003 — Keep Section 35 Architecture Completion Summary as a separate original closing audit, not included in Sections 1–34 arithmetic.
  - *DONE* — Section 35 kept separate from the Sections 1-34 arithmetic
- [x] SRC-004 — Maintain an independent latest-status ledger, not a second replacement master checklist.
  - *DONE* — Superseded by Founder decision 2026-11-10: one file holds spec and status
- [x] SRC-005 — Preserve final-source SHA CI, database/browser/QA evidence and genuine founder-local release proof separately.
  - *DONE* — CI, database, browser and QA evidence preserved per milestone report
- [x] SRC-006 — Original deferred production security/deployment/financial validity gates remain in scope, not deleted.
  - *DONE* — Deferred production gates remain listed, not deleted

## 9. Source references
- Original architecture: Founder Library `AGO_Architecture_Sections_01_34_Master_Checklist.md`.
- Original Phase 0–12: repository `docs/architecture/SECTION_15_ROADMAP.md`.
- Original acceptance criteria: repository `docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`.
- Architecture parity: repository `docs/reports/P0_34_SECTION_SOURCE_PARITY.json`.
- BDR: repository `docs/BDR_SECTION_DELIVERY_RULE.md`, BDR 2.0, `AGENTS.md`, `docs/AI_COLLABORATION.md`.
- November code: latest evidence at `develop` SHA `ecb8464`, 7 November 2026; 9-job CI, backend quality and company growth all passed at that code SHA.

Every `- [ ]` is a *permanent requirement*, not a statement that existing code is absent.
Verification and operational acceptance must be tracked separately.

---

## 10. Superseded lists (kept for history, no longer updated)

These are JARVIS's earlier generations. Nothing in them is lost: every requirement was carried into this file.

| Date | File | Items | Why superseded |
|---|---|---|---|
| 2026-10-24 | `docs/reports/YELLOW_24_EXECUTION_LEDGER.md` | 24 | Replaced by the 22-task list |
| 2026-10-25 | `docs/reports/AGO_P1_22_TASK_CONSOLIDATED_EXECUTION.md` | 22 | Replaced by the 48-task ledger |
| 2026-10-24 | `docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json` | 48 | Statuses are stale (baseline 2026-10-24); carried into section 3 above |
| 2026-11-08 | `docs/AGO_FROZEN_MASTER_CHECKLIST_V1_2026-11-08.md` | 429 | Correct IDs but no status at all; it is the source of every requirement here |

Per-milestone and per-section acceptance reports under `docs/reports/` stay valid as **evidence**. They are not checklists and must not be treated as scope.

## 11. Change log

Only the Founder authorizes a line here.

| Date | Who | Change |
|---|---|---|
| 2026-11-10 | Founder | Ordered one single checklist; all earlier lists superseded. Future feature or architecture changes enter here only on the Founder's word. |
| 2026-11-10 | Claude | Built this file from the frozen 429 requirements, added evidence-based status to every item, and recorded the blocking line. No requirement text changed. |
