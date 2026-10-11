# AGO Sections 21–27 — Integrated Engineering Evidence and Remaining Acceptance

**Status: integrated local beta; FULL FROZEN ACCEPTANCE NOT YET CERTIFIED.** Scope remains `docs/SECTIONS21_27_SCOPE.md`. This is an evidence ledger, not a completion claim. The original Corporate Constitution, Organizational DNA and one-`develop`-branch BDR remain unchanged.

## Actual implementation (existing PostgreSQL, FastAPI, Next.js)
- **21 Operating System:** additive operating-mode history; company/department/employee restrictions; exact-action independent human approval; expiry fails closed; AI-worker lifecycle events (idle, pause, sleep, interrupt, resume/unavailable/terminated); DB triggers on actual governed-task and agent-run launch; read-only capacity-bounded priority preview; idempotent replay denial for altered approval requests.
- **22 Operational Agent State:** real employee identity, manager, tenant and task joins, worker availability history, persisted bounded operational-load snapshots with provenance digest; no subjective consciousness claim, inferred confidence or fake knowledge scores.
- **23 Multi-Level Planning:** nine-horizon hierarchy, individually reviewed root and child plans, bounded dates and child budgets, immutable rows and tenant FKs; existing goal/DAG→task approval remains authoritative.
- **24 Economics:** original virtual-credit ledger retained; additive observed financial *claims* clearly labeled **unverified**, idempotent provider/source/period entries, approved parent-bounded department/employee envelopes; no bank transfer, real invoice verification or fabricated ROI.
- **25 Internal Marketplace:** versioned tenant/department-owned draft asset catalog, publisher/provenance/license/digest; independent human approval for publication and consumption; immutable use history, consumption counts, independently reviewed deprecation and revocation; old consumed evidence retained.
- **26 Evolution:** bounded baseline/candidate evidence comparisons with measured descriptive deltas and provenance SHA-256, immutable observation rows, no automatic promotion/self-modification; existing MetaBrain reviewed suggestions retained.
- **27 Digital Twin:** snapshot-linked immutable read-only scenarios, real tenant AI headcount and source digest, hypothetical layoffs/hiring/shock/failure/cost and explicit noncalibration/coverage; no real action execution.

**Live integration:** `apps/backend/ago/enterprise_store.py`, 29 authenticated `/v1/operations/enterprise/*` API endpoints, registered `EnterpriseOperationsStorePort`, migration `024_enterprise_operations.sql` and runtime-integrity migration `025_enterprise_runtime_integrity.sql`, Next.js Operations & Tools evidence panels and original M1–M12 endpoint contract hashes preserved. Source-linked Section 1/3/5 and additive Section 13 fingerprints prevent unreviewed drift.

**Tests added:** `test_enterprise_domains_21_27.py`, `test_enterprise_storage_21_27.py`, `test_enterprise_http_21_27.py`. Positive and negative checks cover authenticated browser sessions, real PostgreSQL FK constraints, independent human approval, idempotent replay, direct SQL dispatch denial during pause, worker resume, layered budgets, immutable QA/evidence, marketplace approval and retirement, and hypothetical simulations.

## Mandatory remaining gates (do not close just because a helper/API exists)
| Section | Scope item not yet demonstrated end-to-end |
|---|---|
| 21 | Durable fair multi-department reservations and crash/retry workload queues; constitution-bound HR hire/promotion/termination and department organization changes; quantified autonomy levels/escalation; complete organization lifecycle and accessible approval UI |
| 22 | Validated skills/knowledge/evidence/confidence and access-scope awareness, help/refusal and learning references fed back into safe scheduling and visible in employee UI |
| 23 | Strategic goal↔horizon↔approved DAG task propagation, persistent live QA rollups, reviewed versioned replanning after calendar/dependency/budget conflicts |
| 24 | Verified provider billing/storage/tool/time invoices, reconciled bank/revenue and currency settlements, measured opportunity cost/ROI, real spending gates and audited profit optimization; **blocked on trusted external data/credentials** |
| 25 | Actual asset payload storage/reuse compatibility/semver dependency enforcement, delegated access/approval UI, comprehensive usage analytics and deprecation migration impact |
| 26 | Source-linked prompt/architecture/workflow diagnostics, reproducible controlled experiments, reviewed production activation and separately approved rollback with outcome monitoring; no unsafe autonomous code rewrite |
| 27 | Project, people, calendar and deadline snapshots with full synchronization, independently measured forecast calibration/uncertainty, revenue/growth and market response against observed actuals; **blocked on trustworthy outcome data** |

**Original blueprint Sections 15, 17 and 18:** recovered original 6,115-line founder upload, SHA-256 `6589bc4f7e4f30287a61cefe3979b01d0b2a8357e3bb76dd6bb058d9e1daa1c4`; source-verification crosswalk in `SECTIONS15_18_SOURCE_VERIFICATION.md`. Former “source not available” claim is no longer correct; original versus current roadmap divergences remain explicitly disclosed.

## Verification/rollout conditions
No source commit is acceptance without green **final-head** backend, CI Python matrix, real PostgreSQL migrations and negative tests, frontend/JS/browser, Docker/backup/restore, independent QA and local founder acceptance. Never automatically migrate the user's Windows/PostgreSQL instance: take verified backup, explicit operator review, then manually apply additive 024–025. Full financial/provider and calibration gates remain marked external-data blocked until genuine invoices/observations exist. **No cloud account or paid model is required for the remaining local engineering steps.**

This report is intentionally conservative: a successful CI run certifies the tested implementation scope, **not** the unimplemented remaining checklist items above.


## 2026-10-11 subsequent implementation and CI evidence

The initial report above is preserved as a historical state, **not the latest missing-feature list**. This release-candidate implementation adds the following source-linked capabilities without changing Section 29 authority, tenant/RBAC controls, existing M1-M12 endpoints or the frozen architecture:

| Section | New tested implementation |
|---|---|
| 21 | Migration `027_governed_hr_lifecycle.sql`; independent-action-reviewed department creation and safe closure, AI hiring, strict promotion levels, immutable termination, database task/agent dispatch interlock for terminated staff and closed departments, HR history and authenticated API |
| 22 | Migration `026_agent_escalation_planning_feedback.sql`; immutable tenant-bound AI overload/safety/permission assistance requests, independently approved resolution and actual PostgreSQL dispatch blocking until resolved; live worker state includes active help status |
| 23 | The same migration records an immutable, independently approved horizon-plan-to-governed-task link; read-only QA aggregation reports passed/failed/awaiting evidence and does not auto-activate tasks or rewrite plans |
| 24 | Original bounded virtual-credit and separate observed-cost/budget evidence retained; no unsupported claim of externally authenticated invoices or real ROI |
| 25 | Internal catalog publication/reuse enforces exact tenant-owned semver/digest dependencies, bounded manifests and denial of subsequent reuse when a dependency is deprecated/revoked |
| 26 | Migration `028_evolution_and_twin_outcomes.sql`; independent human-reviewed evolution outcomes, immutable decision/rollback evidence, advisory-only applied=false, previous MetaBrain review gates preserved |
| 27 | Scenario now uses **snapshot-captured** workforce rather than mutable live count; immutable independently reviewed later-snapshot comparisons show descriptive observed task deltas and explicit uncalibrated limitations |

**Integrations:** `apps/backend/ago/enterprise_store.py`, `api_operations.py`, port/source/API fingerprint contracts, Next.js/console Tools page (actual safety, HR, evolution and twin evidence), and tests:
- `test_enterprise_assistance_feedback.py`
- `test_enterprise_hr_21.py`
- `test_marketplace_dependency_25.py`
- `test_enterprise_evolution_twin.py`
- updated `test_enterprise_http_21_27.py`.

**Backend quality CI:** source commit `4e0ab58dbc9139ac34f710ad8590bcaf209aa64f`; `https://github.com/rudrasinha05/ago-/actions/runs/38090372467` **SUCCESS**, including 509 passed real PostgreSQL/backend tests, 1 warning, successful lint and architecture audits. The full cross-browser/CI matrix run `38090372397` was still queued at this update; no final-head full acceptance is implied. The earlier commit `9bcf6060` had the same 509 tests pass but failed an unused-import lint rule; that failure was fixed without disabling checks.

**Remaining ORIGINAL gates:** actual fair crash-recoverable cross-department scheduler, binding all HR intent fields to independently reviewed approval details, comprehensive operational agent skill/knowledge/permission evidence and automated safe learning, approved live goal-to-task replanning and calendars, real provider-verified invoices/bank/revenue ROI, stored transferable/reusable asset payloads and end-user lifecycle UI, executed approved policy/prompt changes with genuinely tested rollback, full Digital Twin project/deadline calibration against held-out real observations. These must **remain pending** until implemented and demonstrated. External production Vault/TLS/auditor are separately deferred per owner personal/local-use decision.

**Windows safety:** migrations 023–028 are additive in the repo but **have not been applied on the owner's Windows PostgreSQL**. Existing local data must be backed up, code fast-forward pulled once, stopped writers confirmed, isolated-restore evidence reviewed and explicit migration executed only with founder consent.

**Do not label Sections 21–27 fully complete.** Source/test progress is substantial; full original scoped acceptance and real-world evidence gates remain open.


## 2026-10-11 follow-up: exact review, capacity, reusable content and planning evidence

**Verified source revision:** `a27a9526c104b3216a45f454804c1c6f16129805`. Backend quality workflow
`https://github.com/rudrasinha05/ago-/actions/runs/38093351424` **SUCCESS**:
**524 passed PostgreSQL/Python tests, 1 warning, Ruff lint and architecture audit green**.
Eight-job full release matrix `38093351396` is queued at this evidence timestamp;
do **not** convert this to final batch acceptance until all final-head jobs pass.

- **21 (OOS):** SQL 029 stores immutable *full-payload* HR approval intents (department/name/manager/role/reason); no approved request can be used for different facts. SQL 030 adds transaction-serialized company/department/employee running-task limits, repaired in additive SQL 032 after a real SQL variable-collision regression; source tested. Read-only autonomy assessments use independently reviewed task/QA records, blocking-help status and load to provide conservative advisory tiers **without granting authority**.
- **22 (Agent evidence):** SQL 033 + strengthened SQL 035 store bounded, exact hash-verified preapproval records for skill/knowledge/confidence/risk/learning/permission awareness, requiring a separate active human reviewer. APIs expose confidence as *uncalibrated, human-reviewed reported evidence*, never subjective consciousness or permission escalation; missing evidence stays unknown. Path owner/tenant binding hardened.
- **23 (Planning):** SQL 034 + strengthened SQL 035 establish independent full-payload plan-revision review, immutable version history, stale version rejection, parent budget/calendar bounds and protection of existing descendants/linked task evidence. Effective revision shown in enterprise plan listing and consulted during subsequent child plan creation and task linking; original approved plan and task rows stay immutable. Revisions never automatically execute/approve tasks.
- **25 (Marketplace):** SQL 031 stores actual bounded 1 MiB tenant-scoped immutable asset bytes with SHA-256/catalog digest consistency, draft-only publisher upload, consent-controlled reads and required payload checks before publish/consume. Version dependency and revocation guards from prior batch remain.
- **26/27:** Preserved exact-action human-reviewed evolution outcomes and descriptive historical twin comparisons; no fabricated calibration or silent deployment.

**New negative-path files:** `test_enterprise_hr_21.py`, `test_enterprise_capacity_21.py`, `test_agent_evidence_22.py`, `test_enterprise_plan_revisions_23.py`, `test_enterprise_autonomy_21.py`, `test_marketplace_payload_25.py`. Other prior Section 21–27 tests were rerun in the verified 524-test full backend suite; old M1–M12 tests were not silently disabled.

**Still open under the original frozen acceptance scope:** crash-recoverable fair priority scheduling/worker leasing, end-to-end company lifecycle and role-specific approval UI, source-verified skill and knowledge assessment with safe learning, complete strategy→calendar→task propagation and live QA replan feedback, externally verified invoices/revenue/opportunity cost/ROI and controlled real spend, broader marketplace reuse/version sunset UI, safe approved policy deployment and rollback with outcome monitoring, full organizational Digital Twin projects/calendars and held-out empirical calibration with genuine later outcomes.

**External verification dependencies:** real financial provider statements, observed revenue and a genuine later operational observation series cannot be invented or marked passed; founder explicitly chose personal/local operation, so production cloud/Vault/external audit remains out of current scope.

**Operator safety:** Source migrations 029–035 are additive only. No user's Windows/PostgreSQL data was changed from this chat. Founder must explicitly back up, pull and apply migrations in order on their own machine with stopped writers and a tested restore path. CI PASS is not the same as Windows/local acceptance or 100% completion of Sections 21–27.


## 2026-10-11 additional Section 21 durable fair queue acceptance delta

Existing task/approval/agent architecture was **not replaced**. Migration `036_durable_fair_work_queue.sql` provides tenant-scoped unique idempotent queue entries and immutable lease/release/reconciliation events. Authorized queue admission requires an independently approved still-waiting task. Acquisition uses bounded fair priority with aging and filters paused company/department/employee modes, blocked assistance, terminated workers and M3 prerequisite QA. PostgreSQL tenant-row locks serialize contenders, existing runtime execution-capacity guards still apply to actual execution. Expired work is never automatically re-executed; historical agent attempts prohibit silent side-effect replay. The operator must deliberately execute through the original permission-checked TaskStore/AgentRuntime.

Signed API: `GET/POST /v1/operations/enterprise/work-queue`, `POST /work-queue/claim`, and `POST /work-queue/{queue_id}/release`. Control Center now shows task priority, lifecycle and lease state. Scope checks are source-linked in Section 3/5/13 engineering fingerprints. Negative tests: `apps/backend/tests/test_enterprise_durable_queue_21.py`.

**Verification:** source revision `1425a4bc90e713a9bfceaf569e5d02d2d3847bb2`, backend quality `https://github.com/rudrasinha05/ago-/actions/runs/38093964101` successful with **527 passed tests, 1 warning, successful Ruff lint and engineering architecture audit**. Full eight-job architecture/browser/recovery matrix `38093964085` was in progress when verified. Later UI-only commits and this report require their own final-head CI confirmation.

**Still remaining in full frozen scope:** a self-running opt-in local worker service with crash/retry operational acceptance, full guided organizational life-cycle UI, independently source-validated competence and permission-aware scheduling, automatically propagated strategy-to-calendar-to-approved-task versions, production/provider-verified finance and real ROI, policy/prompt changes with independently reviewed execution/rollback, and real empirical Digital Twin forecast calibration. Do not mark any of these complete merely because an API, stored scenario or review proposal exists.

**Migration/operator status:** SQL 036 and prior additions are present **only in the repository and disposable CI**; founder's Windows database has not been touched. No production deployment, provider invoice or local upgrade is claimed.


## Consolidated remaining local engineering batch — 2026-10-11

See `SECTIONS21_27_FINAL_BATCH.md` for the current source-linked implementation, review workflows, local worker, QA-backed diagnostics and held-out forecast metrics. Historical remaining-feature lists above are superseded only where that report identifies a delivered workflow. Genuine economics, broad longitudinal calibration, continuous autonomous production synchronization and founder Windows acceptance retain their explicit incomplete status. Final source-head CI evidence is pending.
