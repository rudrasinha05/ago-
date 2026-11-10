> **SUPERSEDED on 2026-11-10 by the Founder.**
> The single source of truth is now **`docs/AGO_MASTER_CHECKLIST.md`**, which carries every
> requirement ID and wording from this file **unchanged**, plus an evidence-based status per item.
> This file is kept for history. Do not update it and do not treat it as scope.

# AGO — FROZEN MASTER CHECKLIST v1.0
Freeze date: 2026-11-08 | Project: BABA GROUPS / AGO | Repo: rudrasinha05/ago- | Audit commit: ecb8464

RULE: Requirement IDs, original scope, sequence, and text are frozen. Do not delete,
merge, rename, renumber, or rewrite them. Later progress belongs in a separate
evidence/status register. New approved scope belongs in a separate numbered addendum.

SOURCE BOUNDARY: This snapshot transcribes the recovered 240-point architecture checklist,
the 48 original acceptance gate titles, and founder requirements available in context.
Historical 96-/160-item lists and the full ~6,115-line blueprint must undergo source
crosswalk if exact verbatim parity is later required; do not invent missing source text.

## 0. Original engineering phases — fixed order

- [ ] PH-−1 — Architecture-only blueprint, enterprise design and explicit non-goals.
- [ ] PH-00 — Foundation: monorepo, environment, API/web skeleton, PostgreSQL, Docker, CI.
- [ ] PH-01 — Platform Core: authentication, RBAC, events, plugins, scheduler, gateway, health.
- [ ] PH-02 — Organization OS: Brain, Meta Brain, council, workflow, departments and registry.
- [ ] PH-03 — AI Employees: plan, think, execute, learn, review; governed roles and evidence.
- [ ] PH-04 — Knowledge & Memory: vectors, graph, RAG, consolidation, privacy and retention.
- [ ] PH-05 — Automation: schedules, workflows, approvals, retry, compensation, events.
- [ ] PH-06 — Collaboration: messaging, meetings, notifications, docs and assignments.
- [ ] PH-07 — Intelligence: reasoning, reflection, debates, correction and improvement.
- [ ] PH-08 — Digital Twins: organization, people, finance and risk what-if evaluation.
- [ ] PH-09 — Marketplace: plugins, skills, templates, reusable agents and SDK.
- [ ] PH-10 — Enterprise: tenancy, billing, compliance, audit and recovery.
- [ ] PH-11 — Production: scale, Kubernetes, regional failover, secure deployment (deferred while localhost-only).
- [ ] PH-12 — Research & Comparison: reproducible benchmarks, ablations and uncertainty.

## 1. Original architecture Sections 1–34 — fixed 240 checkpoints

### S01 — Overall System Architecture
- [ ] A01.01 Describe presentation, application, domain, infrastructure and shared layers
- [ ] A01.02 Define responsibilities and clear boundaries for every organizational module
- [ ] A01.03 Define direction of dependencies and forbidden cross-layer coupling
- [ ] A01.04 Implement one working backend-to-database request path
- [ ] A01.05 Define synchronous APIs versus asynchronous command/event flows
- [ ] A01.06 Map end-to-end goal → plan → approval → execution → QA → audit
- [ ] A01.07 Document fault containment, scaling and organizational tenancy

### S02 — High-Level Component Diagram
- [ ] A02.01 Diagram Company Brain, Meta Brain and Executive Council
- [ ] A02.02 Diagram departments, managers and employees
- [ ] A02.03 Diagram OOS, workflow engine and task queue
- [ ] A02.04 Diagram memory, knowledge graph and communication
- [ ] A02.05 Diagram execution, QA, audit, simulation and dashboards
- [ ] A02.06 Diagram infrastructure, data stores and security boundaries
- [ ] A02.07 Implement basic interactions among brain, execution, approval and QA

### S03 — Domain-Driven Design
- [ ] A03.01 Identify all bounded contexts, including identity, strategy, workforce and economics
- [ ] A03.02 Specify aggregates, entities and value objects per context
- [ ] A03.03 Specify repositories, domain/application services and invariants
- [ ] A03.04 Implement tenant-scoped organization, goals and tasks
- [ ] A03.05 Define domain events, context contracts and published languages
- [ ] A03.06 Enforce complete context isolation through architecture-level tests
- [ ] A03.07 Document eventual consistency and cross-context transaction rules

### S04 — Monorepo Architecture
- [ ] A04.01 Create version-controlled backend package and tests
- [ ] A04.02 Create Next.js web application directory
- [ ] A04.03 Create admin, docs and other app shells
- [ ] A04.04 Create all planned /services domains as agreed architecture
- [ ] A04.05 Create /packages/ui, sdk and shared contracts
- [ ] A04.06 Provide deployment, scripts, test and CI directories
- [ ] A04.07 Prevent unintended coupling across monorepo packages

### S05 — FastAPI Backend Architecture
- [ ] A05.01 Serve actual FastAPI routes and signed sessions
- [ ] A05.02 Separate presentation, application, domain and infrastructure concerns
- [ ] A05.03 Apply dependency injection and repository contracts across all modules
- [ ] A05.04 Offer typed validation and uniform business exception semantics
- [ ] A05.05 Provide governance, brain, AI execution, tools and analytics routes
- [ ] A05.06 Define bounded context contracts for future services
- [ ] A05.07 Test principal auth and cross-tenant isolation against PostgreSQL

### S06 — Next.js Frontend Architecture
- [ ] A06.01 Build working responsive eight-workspace browser console
- [ ] A06.02 Create the specified Next.js frontend application
- [ ] A06.03 Formalize UI state, data fetching and router architecture
- [ ] A06.04 Build shared UI design system/component package
- [ ] A06.05 Add executive, department and employee dashboard experiences
- [ ] A06.06 Connect secure session, RBAC and approval interfaces
- [ ] A06.07 Pass live Chromium desktop/mobile acceptance smoke tests
- [ ] A06.08 Complete accessibility and browser/device compatibility acceptance

### S07 — Database Architecture
- [ ] A07.01 Provision PostgreSQL tenant-scoped durable transactional storage
- [ ] A07.02 Maintain checksum-verified ordered SQL migrations
- [ ] A07.03 Introduce Redis only for justified cache/queue use cases
- [ ] A07.04 Build the specified knowledge graph store such as Neo4j
- [ ] A07.05 Implement vector store/embedding index for semantic search
- [ ] A07.06 Implement object storage for documents and artifacts
- [ ] A07.07 Set explicit data retention, indexing and recovery policies
- [ ] A07.08 Validate isolated PostgreSQL backup and restore drill

### S08 — Message Bus and Communication
- [ ] A08.01 Define command, event, query, notification and approval envelopes
- [ ] A08.02 Implement durable database-backed inbox/outbox
- [ ] A08.03 Add event idempotency and tenant envelope validation
- [ ] A08.04 Deploy approved distributed message broker (if required)
- [ ] A08.05 Define retries, dead-letter handling and replay semantics
- [ ] A08.06 Coordinate approvals without bypassing governance
- [ ] A08.07 Add observability for backlog, ordering and poison messages

### S09 — Memory Architecture
- [ ] A09.01 Design employee, department, project and company memory scopes
- [ ] A09.02 Design experience/episodic and short-term memory
- [ ] A09.03 Persist controlled memory records with authorization
- [ ] A09.04 Implement vector memory and semantic search
- [ ] A09.05 Implement memory consolidation, summarization and forgetting
- [ ] A09.06 Link memory to audited evidence and knowledge graph
- [ ] A09.07 Enforce retention, privacy, provenance and correction

### S10 — Security Architecture
- [ ] A10.01 Implement authentication, RBAC and cross-tenant authorization
- [ ] A10.02 Implement independent approval and role separation
- [ ] A10.03 Provide tamper-aware events/audits and session revocation
- [ ] A10.04 Manage secrets with external production vault and rotation
- [ ] A10.05 Deploy trusted HTTPS ingress and database encryption operations
- [ ] A10.06 Provide MFA/SSO and secure employee invitation/recovery
- [ ] A10.07 Complete external security assessment, threat model and compliance controls
- [ ] A10.08 Use production-safe fail-closed config checks

### S11 — Deployment Architecture
- [ ] A11.01 Build runnable unprivileged Docker release candidate
- [ ] A11.02 Provide localhost Docker Compose preview with PostgreSQL
- [ ] A11.03 Test migration, app and browser regression in CI
- [ ] A11.04 Implement reviewed Kubernetes/Helm/cluster deployment
- [ ] A11.05 Implement service metrics, traces, logging aggregation and alerts at production level
- [ ] A11.06 Implement trusted public TLS gateway and rollout strategy
- [ ] A11.07 Verify real hosted backup, restore and on-call processes

Section 11 additional local-use acceptance, preserved:
- [ ] A11.L01 Guarded loopback-only startup with explicit schema checks and no automatic migrations.
- [ ] A11.L02 Bounded local liveness/readiness/latency probes and actionable failure exit code.
- [ ] A11.L03 Guarded local custom-format backup with no overwrite and integrity manifest.
- [ ] A11.L04 Actual separate empty PostgreSQL restore and restored schema verification.
- [ ] A11.L05 Nonroot Docker/loopback preview regression verification.
- [ ] A11.L06 Windows operator guide and safe update/rollback workflow with matching object recovery.
- [ ] A11.L07 Existing architecture, browser, build, identity, model and storage behavior preserved by CI.

### S12 — Technology Decisions
- [ ] A12.01 Record explicit technology choices for frontend/backend/database/broker
- [ ] A12.02 Document rationale, alternatives and trade-offs
- [ ] A12.03 Record performance, operational and financial consequences
- [ ] A12.04 Capture ADRs with status, approval and supersession
- [ ] A12.05 Choose and use initial FastAPI + PostgreSQL + Docker stack
- [ ] A12.06 Govern dependency upgrades and technology replacement

### S13 — Coding Standards and Quality
- [ ] A13.01 Enforce automated Python linting in CI
- [ ] A13.02 Exercise Python/PostgreSQL unit and integration tests
- [ ] A13.03 Exercise JavaScript template/security tests and live browser tests
- [ ] A13.04 Document naming, formatting, versioning and errors for all languages
- [ ] A13.05 Implement cross-module security and coverage thresholds
- [ ] A13.06 Add reliable API, contract, performance and regression quality gates
- [ ] A13.07 Provide release versioning and stable compatibility policy

### S14 — Module Dependency Rules
- [ ] A14.01 Define which bounded contexts can depend on which other contexts
- [ ] A14.02 Define forbidden imports and circular dependency rules
- [ ] A14.03 Keep approved/QA state changes behind governed domain boundaries
- [ ] A14.04 Introduce architecture tests/CI checks for forbidden dependency edges
- [ ] A14.05 Specify API/event contracts when modules are extracted
- [ ] A14.06 Maintain versioned and reviewed exception policy

### S15 — Implementation Roadmap
- [ ] A15.01 List original engineering phases 0–12 and acceptance conditions
- [ ] A15.02 Map every architecture section to implementing milestone and owner
- [ ] A15.03 Capture M1–M12 completed bounded increments and CI evidence
- [ ] A15.04 Maintain dependencies, blockers and security signoffs
- [ ] A15.05 Provide backlog for missing enterprise and research work
- [ ] A15.06 Verify implementation parity against complete original blueprint

### S16 — Architecture Governance
- [ ] A16.01 Define architecture authority and separation of technical decisions
- [ ] A16.02 Define approval thresholds and ADR amendment process
- [ ] A16.03 Define baseline freeze, exception and compatibility reviews
- [ ] A16.04 Enforce independent approval for operational tasks
- [ ] A16.05 Track cross-system architecture changes and review evidence
- [ ] A16.06 Periodically audit implementation against frozen specification

### S17 — Phase −1 Non-Goals
- [ ] A17.01 Specify work intentionally excluded from Phase −1 design
- [ ] A17.02 Prohibit business logic during architecture-only phase
- [ ] A17.03 Separate research ambitions from bounded deliverables
- [ ] A17.04 Document risks from unsupported scope expansions
- [ ] A17.05 Independently inspect the original full blueprint section for fidelity

### S18 — Reference Technology Sources
- [ ] A18.01 Cite primary documentation for the selected engineering stack
- [ ] A18.02 Reference FastAPI, Next.js, PostgreSQL, Docker and deployment patterns
- [ ] A18.03 Reference security and distributed systems standards and alternatives
- [ ] A18.04 Record source version/date and rationale for decisions
- [ ] A18.05 Check original full blueprint bibliography for accuracy

### S19 — Meta Brain
- [ ] A19.01 Observe Company Brain decisions without directly taking control
- [ ] A19.02 Record evidence-based executive snapshots and recommendations
- [ ] A19.03 Implement long-term reflection and effectiveness evaluation
- [ ] A19.04 Assess organization, architecture, departments, workforce and workflows
- [ ] A19.05 Propose improvements and maintain human approval gates
- [ ] A19.06 Verify before/after organizational change outcome quality

### S20 — Organizational DNA
- [ ] A20.01 Define mission, vision and values as governed profile
- [ ] A20.02 Define leadership, engineering and research philosophy
- [ ] A20.03 Define communication, innovation, risk and documentation philosophy
- [ ] A20.04 Define hiring, promotion, meeting, learning and quality philosophy
- [ ] A20.05 Version and human-approve bounded threshold DNA changes
- [ ] A20.06 Implement employee/department inheritance and allowed overrides
- [ ] A20.07 Prevent DNA policy from overriding corporate constitution

### S21 — Organizational Operating System
- [ ] A21.01 Schedule tasks and run bounded workflows
- [ ] A21.02 Allocate workload, resources and priorities across departments
- [ ] A21.03 Support pause, sleep, idle, interrupt and resume states
- [ ] A21.04 Govern hiring, promotion, termination and organizational changes
- [ ] A21.05 Define emergency and maintenance operating modes
- [ ] A21.06 Calculate autonomous operating levels and escalation
- [ ] A21.07 Maintain full organization-level lifecycle state machine

### S22 — Agent Consciousness / State Model
- [ ] A22.01 Register identity, role, manager and basic assigned tasks
- [ ] A22.02 Track future assignments, goals and plan dependencies
- [ ] A22.03 Track confidence, skills, knowledge, risk and permission awareness
- [ ] A22.04 Track workload, stress, availability and assistance needs
- [ ] A22.05 Implement escalation thresholds, refusal and overload safeguards
- [ ] A22.06 Track learning status and state changes with evidence
- [ ] A22.07 Ensure state does not claim subjective machine consciousness

### S23 — Multi-Level Planning
- [ ] A23.01 Represent tenant goals, dependent plan steps and execution approvals
- [ ] A23.02 Model lifetime vision and five-year company goals
- [ ] A23.03 Propagate annual, quarterly, monthly, weekly, daily and hourly plans
- [ ] A23.04 Propagate top-level strategic objectives to task scheduling
- [ ] A23.05 Aggregate execution/QA outcomes as upward planning feedback
- [ ] A23.06 Re-plan safely against budgets, calendars and dependencies

### S24 — Organizational Economics
- [ ] A24.01 Enforce a tenant virtual-credit budget and usage ledger
- [ ] A24.02 Simulate bounded credit consumption and failure risk
- [ ] A24.03 Measure real model, storage, execution, tool and time expenses
- [ ] A24.04 Measure opportunity costs and observed return on investment
- [ ] A24.05 Assign governed department and employee budgets
- [ ] A24.06 Reconcile company budgets with actual invoices and revenue
- [ ] A24.07 Optimize for audited real-world cost and profit with controls

### S25 — Internal Marketplace
- [ ] A25.01 Build service/library/dataset/research asset publishing catalog
- [ ] A25.02 Build reusable models, workflows, agents and template listings
- [ ] A25.03 Track publishers, ownership, versions, licenses and access policies
- [ ] A25.04 Support discovery, approval and controlled cross-department reuse
- [ ] A25.05 Implement consumption analytics and lifecycle deprecation
- [ ] A25.06 Distinguish internal asset exchange from a paid external marketplace

### S26 — Evolution Engine
- [ ] A26.01 Collect QA, failure, bottleneck and performance observations
- [ ] A26.02 Measure prompt, architecture, workflow and department quality
- [ ] A26.03 Propose bounded policy improvements with human review
- [ ] A26.04 Compare controlled experiment baseline and candidate outcomes
- [ ] A26.05 Audit approvals, rollbacks and promotion of changed policies
- [ ] A26.06 Never allow uncontrolled self-modification or privilege escalation

### S27 — Digital Twin
- [ ] A27.01 Capture current evidence snapshots for organizational comparison
- [ ] A27.02 Run bounded what-if scenarios without applying policies
- [ ] A27.03 Model projects, departments, employees, availability and deadlines
- [ ] A27.04 Model hiring, layoffs, growth, market shocks, revenue and risk
- [ ] A27.05 Calibrate predictions against observed outcomes and uncertainty
- [ ] A27.06 Keep production/twin state synchronized with provenance
- [ ] A27.07 Require human authorization before any real-world action

### S28 — Architecture Differentiators
- [ ] A28.01 Compare architectural intent with CrewAI and AutoGen
- [ ] A28.02 Compare with LangGraph and OpenHands
- [ ] A28.03 Compare with traditional BPM, ERP and project management
- [ ] A28.04 Explain organization-level governance versus task-agent orchestration
- [ ] A28.05 Support comparative claims with reproducible experiments
- [ ] A28.06 Review exact original V2 section and citations for accuracy

### S29 — Corporate Constitution
- [ ] A29.01 Define constitutional purpose and highest policy priority above DNA
- [ ] A29.02 Define organizational laws and immutable non-negotiable rules
- [ ] A29.03 Specify founder, humans, councils and AI separation of powers
- [ ] A29.04 Implement checks, balances and cross-subsystem policy enforcement
- [ ] A29.05 Implement independent approval and QA guardrails
- [ ] A29.06 Define amendment voting, effective dates, versioning and audit
- [ ] A29.07 Implement narrowly constrained emergency constitutional procedures
- [ ] A29.08 Prove every module cannot override or bypass constitutional policy

### S30 — Organizational Calendar
- [ ] A30.01 Create tenant-visible/private events and invitation responses
- [ ] A30.02 Model working hours, time zones and holiday calendar
- [ ] A30.03 Model weekly sprints and monthly/quarterly/annual cycles
- [ ] A30.04 Manage company budgets, hiring, promotion and performance-review calendars
- [ ] A30.05 Schedule maintenance, incident response and release freeze windows
- [ ] A30.06 Schedule simulations and employee learning cycles
- [ ] A30.07 Synchronize department plans, task deadlines and long-running workflows
- [ ] A30.08 Enforce conflicts, quiet hours, rescheduling and calendar governance

### S31 — Enterprise Knowledge Graph
- [ ] A31.01 Propose independently verified fact/policy/artifact/decision nodes
- [ ] A31.02 Create limited supports/contradicts/depends_on/references relationships
- [ ] A31.03 Model people, departments, projects, customers, products and assets
- [ ] A31.04 Model workflows, research, models, skills, tools, incidents and documents
- [ ] A31.05 Link memory, audit and decision references with provenance
- [ ] A31.06 Implement rich typed graph queries and path traversals
- [ ] A31.07 Define versioned graph evolution, merging, deletion and tenant ACLs
- [ ] A31.08 Synchronize comprehensive graph with memory architecture

### S32 — Organizational Psychology
- [ ] A32.01 Define measurable trust, reliability and leadership signals
- [ ] A32.02 Define collaboration, communication style and mentoring scores
- [ ] A32.03 Define decision bias, creativity, risk behavior and learning velocity
- [ ] A32.04 Define adaptability, conflict resolution and promotion readiness
- [ ] A32.05 Validate behavioral measurements for accuracy, privacy and bias
- [ ] A32.06 Specify human review and appeal before assignment/promotion/autonomy changes
- [ ] A32.07 Log signal evolution, drift and expiry over time

### S33 — Enterprise Analytics
- [ ] A33.01 Compute organization/task/run counts, virtual budgets and risk flags
- [ ] A33.02 Provide executive/strategy overview in Control Center
- [ ] A33.03 Implement departmental and employee analytics dashboards
- [ ] A33.04 Implement finance, workflow, QA and security dashboards in full
- [ ] A33.05 Implement architecture, infrastructure, knowledge and memory dashboards
- [ ] A33.06 Implement innovation, Digital Twin, Meta Brain and health dashboards
- [ ] A33.07 Implement KPI definitions, lineage, forecasting and anomaly detection
- [ ] A33.08 Implement scheduled executive reports, alerts and governance

### S34 — Company API Platform
- [ ] A34.01 Provide tenant-scoped versioned REST endpoints with RBAC
- [ ] A34.02 Provide production API gateway, traffic policy and rate controls
- [ ] A34.03 Implement streaming/event subscription APIs with stable schemas
- [ ] A34.04 Implement signed, replay-protected webhooks and retry queues
- [ ] A34.05 Implement public/partner OAuth clients and scoped API keys
- [ ] A34.06 Publish typed multi-language SDKs and developer portal
- [ ] A34.07 Build plugin and third-party enterprise integration lifecycle
- [ ] A34.08 Create API versioning/deprecation/compatibility governance

## 2. Original 48-task P0/P1/P2 acceptance ledger — existing IDs and criteria

These are **additional, original, narrower release gates** in the repository. The
original IDs and acceptance wording are unchanged. Historical status remains in
`docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`; don't edit this specification
merely to raise a percentage. Some gate numbers are non-contiguous by design.

### P0 — Core integrity and original parity
- [ ] ACC-10 — Local security architecture | Verify secrets, RBAC and data minimization across source, API, logs and backups
- [ ] ACC-14 — Module dependency rules | All architectural source/import checks and protection policies enforced
- [ ] ACC-15 — Original implementation roadmap parity | Original frozen plan traced to implemented modules and signed acceptance
- [ ] ACC-17 — Phase −1 non-goal reconciliation | Explicitly record deferred external/production work against original blueprint
- [ ] ACC-18 — Technology reference parity | Every original technology claim verified or identified as a scoped alternative
- [ ] ACC-36 — 34-section implementation parity | All 34 original architecture deliverables matched to source and tested behavior
- [ ] ACC-45 — All-module integration | Same-SHA backend, database, browser and cross-module journey all green
- [ ] ACC-120 — Approval and authority compatibility | Founder, independent QA and bounded CEO authorization all pass integration
- [ ] ACC-133 — Confidential information leak prevention | Unauthorized tenant/project/employee access and export path tests fail closed
- [ ] ACC-134 — Project document and tool data isolation | Unapproved project worker cannot read private bodies via any public endpoint
- [ ] ACC-156 — Reports, search, tools, logs and backup redaction | No secret or founder brief can leak through persisted evidence or any export
- [ ] ACC-158 — Latest same-SHA complete CI | Entire nine-job architecture plus backend, lint and browser green at final head

### P1 — Autonomous company and AI workforce
- [ ] ACC-19 — Meta Brain real recommendation loop | Compute source-backed changes with independent review and actual outcome metrics
- [ ] ACC-21 — Organizational operating system execution | Approved task schedule, dispatch, lifecycle and concurrency reflect real work
- [ ] ACC-22 — Truthful AI employee state | Worker idle, running, blocked and failed statuses all derive from durable execution
- [ ] ACC-23 — Executable multi-level project planning | Founder goal delegated as authorized executable dependency-aware task graph
- [ ] ACC-26 — Governed autonomous evolution engine | Measured reviewed improvement proposal with rollback and no silent code writes
- [ ] ACC-48 — Large interactive 3D Company Brain | True interactive 3D scene linked to source-backed actual running tasks
- [ ] ACC-58 — CEO to CTO to PM to engineer delegation | Real identities, real scoped handoffs, independently authorized task starts
- [ ] ACC-60 — Controlled automatic staffing | Bounded CEO-chartered personnel proposal without duplicate roles or privilege escalation
- [ ] ACC-61 — Multi-agent real teamwork | Multiple distinct AI workers complete linked subtasks and report evidence
- [ ] ACC-87 — LLM-generated executable project plan | Real local model proposes viable milestones assessed and activated by Founder
- [ ] ACC-119 — Revocable CEO operational charter | Scoped capabilities, term, budgets, audit and immediate human revocation
- [ ] ACC-123 — Meta Brain measured improvements | Measured failed work feeds reviewed improvements with independent QA
- [ ] ACC-125 — Tenant-scoped enterprise tool execution | Approved safe tools execute under employee-specific scopes with audit trail
- [ ] ACC-126 — Active local worker monitoring | Live health and durable incident notifications with no fictitious activity
- [ ] ACC-127 — Model, task and resource budgets | CPU/memory/time/token ceilings with budget-exhaustion negative tests
- [ ] ACC-128 — Crash-safe failure reconciliation | Unknown external outcome never repeated; safe operator reconciliation documented
- [ ] ACC-135 — Real work driven Brain visualizations | Progress, red paths and worker highlights reflect actual signed work receipts
- [ ] ACC-138 — All employee task event popups | Each recorded work transition has durable counted event and accessible popup
- [ ] ACC-139 — Local Ollama multi-role governed chain | All seven full-Board/personnel roles run in authorized scoped sequence
- [ ] ACC-140 — Actual founder laptop local model verification | Owner Windows Ollama inference measured with model, device and identity evidence
- [ ] ACC-152 — Bounded continuous active employee work | Founder-started local process runs multiple approved tasks safely while powered on
- [ ] ACC-154 — Reliable interrupted execution recovery | Restarted worker resumes only safe queued work and does not duplicate unknown writes

### P2 — Real software production, handover and maintenance
- [ ] ACC-92 — AGO-owned governed GitHub CI operations | Tenant-authorized repo-scoped commit, draft PR and read-only exact SHA CI inspection
- [ ] ACC-94 — Independent full-project QA | Human reviewer validates complete requirements and real artifact test evidence
- [ ] ACC-96 — Complete usable software from approved brief | Real supported project generated, built and delivered from Founder request
- [ ] ACC-97 — Automatic bug diagnosis and safe repair | Failed isolated tests generate reviewed source-only repair without rewriting tests
- [ ] ACC-98 — Versioning, release and maintenance lifecycle | Reviewed local release, rollback instructions and tracked maintenance
- [ ] ACC-129 — Real founder laptop backup/restore drill | Safe owner-controlled backup, isolated restore and integrity report on real local DB
- [ ] ACC-130 — Complete real local acceptance | Signed-in Founder demonstration of all authorized core journeys on Windows
- [ ] ACC-147 — AGO GitHub repository-scoped credentials | Owner configures local token/binding privately, never sent to chat or model
- [ ] ACC-148 — True AGO-origin GitHub commit and draft PR | AGO backend executes independently approved write with matching durable receipt
- [ ] ACC-149 — Independent human PR/QA review | Distinct authenticated human acceptance of test and exact artifact/source SHA
- [ ] ACC-150 — Owner laptop signed-in browser and device QA | Live locally installed AGO passes Founder browser, data and permissions checks
- [ ] ACC-155 — Web, Android and full-stack supported adapters | Each supported output type has real build/test/install evidence; no universal claims
- [ ] ACC-159 — Full independent final product QA | Complete artifact passes functional, security, accessibility and regression review
- [ ] ACC-160 — Founder-accepted usable project handover | Actual working local product, immutable acceptance and explicit owner release decision

## 3. Later founder requests — fixed additive subrequirements

These points capture requirements and corrections made during the company-map,
Ollama, Claude/Ultron, multi-project and governance discussions. They refine
rather than replace original architecture points. Similar language across a
section and a founder amendment indicates traceability, not a reason to merge.

### FND — BABA GROUPS founder vision
- [ ] FND-001 — AGO must function as central infrastructure for many independent startups/projects, not just another AI app.
- [ ] FND-002 — Founder directs organizational strategy, priorities, budgets and consequential decisions.
- [ ] FND-003 — AGO plans, develops, runs, maintains and monitors many projects with separate actual teams.
- [ ] FND-004 — Later verified monetization, sales and support belong to each product's business operations.
- [ ] FND-005 — Multi-model orchestration work forms a compatible part of AGO, not an unrelated discarded project.
- [ ] FND-006 — BABA GROUPS also intends diversified ventures and investment in external founders, subject to future governance.
- [ ] FND-007 — The number of future projects is not fixed; project registration must be extensible.
- [ ] FND-008 — AGO itself is built first; other projects remain queued until real execution works.

### BDR — Development rulebook, scope and coordination
- [ ] BDR-001 — Freeze all original approved architecture/phase/requirement IDs and wording.
- [ ] BDR-002 — Never silently replace, delete, merge or shorten original requirements.
- [ ] BDR-003 — Changes of scope require a separate append-only request and founder authorization, not an edited master checklist.
- [ ] BDR-004 — No mid-project architecture changes merely because an agent invents a better idea.
- [ ] BDR-005 — Make substantial milestone delivery in one batch: code, integration, tests, failures, fix, retest, evidence.
- [ ] BDR-006 — Continue safe routine reversible work autonomously; only high-risk actions interrupt Founder.
- [ ] BDR-007 — Never report fake production completion, imaginary employee thought/activity or synthetic revenue.
- [ ] BDR-008 — Preserve existing working code, migrations, databases, user data, tests and architecture boundaries.
- [ ] BDR-009 — Read actual repository, Git head, GitHub issues and assistant ownership before editing.
- [ ] BDR-010 — No destructive reset, force-push, unapproved rollout or secret disclosure.
- [ ] BDR-011 — Keep develop as implementation branch and main as owner-reviewed release branch under existing project collaboration rules.
- [ ] BDR-012 — Status must be evidence-based and include exact tests, CI SHA, pending dependencies and known failures.
- [ ] BDR-013 — Independent review/QA policies cannot be bypassed by UI labels or agent self-approval.
- [ ] BDR-014 — Do not require Founder to answer 'continue' after every tiny internal patch.
- [ ] BDR-015 — Never quietly modify this frozen specification; status belongs only in a separate progress ledger.

### ORG — Physical-company-style management by actual AI employees
- [ ] ORG-001 — Founder is the one intended human owner; executive/worker AI identities must be real stored software identities.
- [ ] ORG-002 — Support CEO, CTO, CFO, CISO, CQO and optional COO, CAIO, CPO, CMO, CHRO and other justified roles.
- [ ] ORG-003 — Explicit founder-appointed five-seat Board, without granting accidental runtime privileges.
- [ ] ORG-004 — Every employee has role title, core responsibilities, extra responsibilities and actual reporting manager.
- [ ] ORG-005 — Project-specific manager/stage worker and project name must be attributable to real records.
- [ ] ORG-006 — Operational task approval follows manager/senior → PM → CEO by authorized hierarchy and scope.
- [ ] ORG-007 — Company-level major decisions and exceptional approvals escalate to Founder.
- [ ] ORG-008 — Board denial must show the denying seat, reasons, vote and exact scope.
- [ ] ORG-009 — Under CEO+CTO approval, eligible Finance/Risk/Quality Board veto may be explicitly Founder-overridden with immutable evidence.
- [ ] ORG-010 — Denied proposal is revised and resubmitted, not automatically abandoned.
- [ ] ORG-011 — Project Manager should rewrite denied scope to address the actual recorded feedback.
- [ ] ORG-012 — Automatically propose/authorize suitable staffing for an unstaffed project stage without duplicates or privilege escalation.
- [ ] ORG-013 — CEO operational charter must be revocable, scope-bounded, time-bounded, budgeted and audited.
- [ ] ORG-014 — AI employees send upward blocker, doubt, module-done and phase-done reports to their real manager.
- [ ] ORG-015 — Distinguish private manager reporting from tenant-visible company chat.

### VIS — Founder visual control center and Brain
- [ ] VIS-001 — Large interactive genuine 3D Brain representing actual organization nodes and real activity.
- [ ] VIS-002 — A worker actively running a recorded task gets a red border until real task execution ends.
- [ ] VIS-003 — Only actual involved reporting/task links illuminate red; idle or unrecorded links do not.
- [ ] VIS-004 — Show the project title on each relevant working employee.
- [ ] VIS-005 — Display actual employee/department hierarchy, roles and assigned tasks in a pannable and zoomable company map.
- [ ] VIS-006 — Differentiate idle, proposed, waiting, running, failed, blocked and unknown states.
- [ ] VIS-007 — Never present model thinking as continuously active without persisted execution evidence.
- [ ] VIS-008 — Source-backed WebGL Brain and a usable fallback when GPU/browser cannot use WebGL.
- [ ] VIS-009 — Every employee must have durable counted work events and numbered popup notifications.
- [ ] VIS-010 — Separate per-employee lifetime counts from unread/read-cursor counts.
- [ ] VIS-011 — No notification or event may be permanently lost just because the Founder closes/reopens the browser.
- [ ] VIS-012 — Founder portfolio lists all projects with status, team, progress, evidence and verified income (if any).
- [ ] VIS-013 — Clicking a project opens all authorized details: tasks, history, documents, code, approvals, QA, GitHub, budget and delivery.
- [ ] VIS-014 — Active forms, log panels and running task progress survive periodic UI refresh.
- [ ] VIS-015 — Company Chat and employee conversations are grounded in real stored project/task data.
- [ ] VIS-016 — Accessibility, mobile/tablet and browser keyboard-navigation acceptance must cover key Founder controls.

### PROJ — Multi-project orchestration and continuation
- [ ] PROJ-001 — Founder submits a brief; AGO persists a project goal, plan, tasks and actual accountable manager.
- [ ] PROJ-002 — Deliver discovery → architecture → implementation → QA → release with explicit dependencies.
- [ ] PROJ-003 — Real project team is selected/assigned based on role, skill and availability.
- [ ] PROJ-004 — Do not fake an assignment or create an executable task merely from a suggested assignee.
- [ ] PROJ-005 — Founder can view next safe step or run bounded 'keep going until I am needed'.
- [ ] PROJ-006 — Automatic next-stage approval, dispatch, QA and continuation should be durable server-side, not dependent on an open browser.
- [ ] PROJ-007 — Keep the Founder informed of actual work, blockers, retries, decisions and QA results.
- [ ] PROJ-008 — Failure classifications distinguish Board denial, code invalid, QA FAIL, timeout, credit, unstaffed and unknown outcome.
- [ ] PROJ-009 — Recover failed tasks by creating new approved attempts and preserving old audit/QA evidence.
- [ ] PROJ-010 — Multiple independent projects should execute concurrently with task-level fairness, isolation and budget limits.
- [ ] PROJ-011 — Project isn't genuinely DONE merely because the AI generated stage text or UI shows a green badge.
- [ ] PROJ-012 — Preserve existing project approvals, artifacts and history through reassignment and upgrades.
- [ ] PROJ-013 — Track statuses separately for development, internal review, release, maintenance and measured commercial results.

### AI — LLM orchestration and actual worker execution
- [ ] AI-001 — Support explicit authorized connectors for Ollama, OpenAI, Gemini, Claude and future providers.
- [ ] AI-002 — Consumer ChatGPT/Claude quota is not a transferable token balance for another provider.
- [ ] AI-003 — Seven distinct Board/PM/worker identities can run their bounded sequential inference roles with receipts.
- [ ] AI-004 — Work output must derive from actual authorized model inference, not a hardcoded fabricated response.
- [ ] AI-005 — Real engineering workers must produce validated source files, matching tests and required docs.
- [ ] AI-006 — Validate path allowlists, content limits, syntax, source hash and API shape before staging code.
- [ ] AI-007 — Attempt bounded self-correction after invalid code and classify continued invalidity safely.
- [ ] AI-008 — Model credits, context, tokens, timeouts, CPU/GPU and memory limits must be controlled/measured where possible.
- [ ] AI-009 — Founder Windows Ollama inference requires actual local proof, not a mocked provider test.
- [ ] AI-010 — Models only execute tools permitted by company policy and the exact project/employee authority.
- [ ] AI-011 — Capture source-bound model, worker, task, handoff, failure and evidence receipts.
- [ ] AI-012 — No uncontrolled self-improvement, model-made architecture rewrite or autonomous privilege expansion.

### QA — Software, sandbox, correction and verified delivery
- [ ] QA-001 — Generated code must be staged separately without overwriting trusted existing source.
- [ ] QA-002 — Execute candidate code/tests in an isolated non-root, no-network, resource-bounded Docker container.
- [ ] QA-003 — Real tests must run; zero-test success or synthetic pass must not count as software acceptance.
- [ ] QA-004 — Preserve source digests, exact test evidence, failure category and bounded private-output redaction.
- [ ] QA-005 — Source-only repair after test FAIL cannot rewrite original tests or bypass approvals.
- [ ] QA-006 — A repaired candidate must be retested in a fresh authorized attempt; retain all original FAIL evidence.
- [ ] QA-007 — AI-stage QA is different from executed-code testing, final independent review and actual release approval.
- [ ] QA-008 — Project acceptance covers functionality, privacy, security, accessibility, dependencies and regression tests.
- [ ] QA-009 — Complete one real project from Founder brief through actual executable artifact and final review, not just mocked CI.

### GIT — AGO-owned GitHub and market-ready delivery
- [ ] GIT-001 — Bind each project to reviewed actual GitHub repository identity, owner, visibility and branch.
- [ ] GIT-002 — AGO's own GitHub runtime credentials are separate from ChatGPT's GitHub connector.
- [ ] GIT-003 — Source commits must be reviewed, exact-parent, non-force writes with durable identity receipts.
- [ ] GIT-004 — GitHub CI must prove named required checks on the exact final source SHA.
- [ ] GIT-005 — Only then create a reviewable Draft PR with exact source and tests; no unapproved auto-merge.
- [ ] GIT-006 — Never retry uncertain GitHub writes blindly; inspect result and reconcile safely.
- [ ] GIT-007 — UI shows real commit, PR, CI, QA and final Founder action, not a fabricated green state.
- [ ] GIT-008 — Existing GitHub projects and code must be reused, not duplicated into a different project silently.
- [ ] GIT-009 — Live AGO-origin delivery is distinct from a human/Claude/ChatGPT developer manually pushing AGO code.

### LOC — Windows localhost, database and genuine data protection
- [ ] LOC-001 — Founder decides when AGO/Ollama/worker/server runs and when laptop is awake/off.
- [ ] LOC-002 — Read-only inspect actual database and applied migration versions before any upgrade.
- [ ] LOC-003 — Find and prevent all unwanted seed, mock, test fixture or placeholder record insertion into founder DB.
- [ ] LOC-004 — Test/CI data must use isolated disposable databases and restricted credentials.
- [ ] LOC-005 — Verify database and private-object backup integrity and isolated restore before destructive changes.
- [ ] LOC-006 — Never delete suspicious records simply because they appear dummy; confirm provenance and Founder decision.
- [ ] LOC-007 — Verify actual Windows login, PostgreSQL, Ollama, server, browser, 3D GPU, worker and task results.
- [ ] LOC-008 — Check git remote configuration separately from historical origin/develop refs.
- [ ] LOC-009 — No unapproved paid API calls, cloud deployment, auto-wake, startup daemon or public publication.
- [ ] LOC-010 — Preserve historical migrations and company data; apply only verified additive owner-authorized changes.

### BUS — Business development, release and operation
- [ ] BUS-001 — Differentiate virtual AI credits from authentic invoices, customer receipts, net profit and ROI.
- [ ] BUS-002 — Run company/project analytics on real events rather than imaginary income and worker productivity.
- [ ] BUS-003 — Research and market-opportunity proposals must be labelled hypotheses until evidence validates demand.
- [ ] BUS-004 — Real marketing, pricing, sales, customer service and maintenance need accountable authorized employees.
- [ ] BUS-005 — Track bug reports, post-launch repairs, releases, rollback and support outcomes.
- [ ] BUS-006 — Integrate new ventures and founder investment decisions as separate governed company projects.

### QUEUE — Known projects to be onboarded by AGO later
- [ ] QUEUE-001 — AdmissionFlow as a real end-to-end AGO software-delivery pilot.
- [ ] QUEUE-002 — CUE Android AI Reminder App, with its original separate project and delivery gates.
- [ ] QUEUE-003 — BTS Android / Baba Tiffin Service, reusing its pre-existing backend and requirements.
- [ ] QUEUE-004 — AI Task Manager / Windows RAM optimizer with fundamental system-process safety.
- [ ] QUEUE-005 — MANCH, AI Shopping Agent, Make India Clean and multi-model orchestration research projects.
- [ ] QUEUE-006 — BABA local AI assistant / Ollama customization, deferred until approved.
- [ ] QUEUE-007 — Department Workflow Automation: attendance, timetable, notices, exams, faculty workload, student follow-up, reports and approvals.
- [ ] QUEUE-008 — Unlimited future approved projects can be registered without silently modifying this frozen AGO architecture.

## 4. Exact source-recovery and evidence gates
- [ ] SRC-001 — Crosswalk the full previously recovered ~6,115-line original Sections 0–35 blueprint verbatim.
- [ ] SRC-002 — Recover earlier 96- and 160-item checklists in full and record unmatched historical wording without rewriting v1.0.
- [ ] SRC-003 — Keep Section 35 Architecture Completion Summary as a separate original closing audit, not included in Sections 1–34 arithmetic.
- [ ] SRC-004 — Maintain an independent latest-status ledger, not a second replacement master checklist.
- [ ] SRC-005 — Preserve final-source SHA CI, database/browser/QA evidence and genuine founder-local release proof separately.
- [ ] SRC-006 — Original deferred production security/deployment/financial validity gates remain in scope, not deleted.

## 5. Source references
- Original architecture: Founder Library `AGO_Architecture_Sections_01_34_Master_Checklist.md`.
- Original Phase 0–12: repository `docs/architecture/SECTION_15_ROADMAP.md`.
- Original acceptance criteria: repository `docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`.
- Architecture parity: repository `docs/reports/P0_34_SECTION_SOURCE_PARITY.json`.
- BDR: repository `docs/BDR_SECTION_DELIVERY_RULE.md`, BDR 2.0, `AGENTS.md`, `docs/AI_COLLABORATION.md`.
- November code: latest evidence at `develop` SHA `ecb8464`, 7 November 2026; 9-job CI, backend quality and company growth all passed at that code SHA.

Every `- [ ]` is a *permanent requirement*, not a statement that existing code is absent.
Verification and operational acceptance must be tracked separately.