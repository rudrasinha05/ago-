# AGO · founder-directed execution ledger for 24 yellow items

Scope: original founder 96-item checklist's **22 yellow** entries plus
**2 yellow confidentiality/document items** from the added document checklist.
This is an exact frozen worklist for the instruction "complete all 24; suspend
an item when blocked and continue to the next". It does not reclassify white
commercial tasks into the original checklist.

**Status contract: ONLY COMPLETED or SUSPENDED.**
- **COMPLETED:** bounded checklist capability has actual source and at least one
  relevant passed integration/security/browser CI, with evidence and scope documented.
- **SUSPENDED:** full original requirement still has a missing acceptance gate.
  Work that has been coded but is not fully demonstrated is SUSPENDED, not half-green.
- Suspend a blocked task and continue to other work; never fabricate permissions,
  autonomous staff, test verdicts, hosting uptime or business outcomes.

| Item | Status | Bounded evidence / unfinished acceptance |
|---|---|---|
| 01 · #2 Sections 1–34 | SUSPENDED | Section documentation and local architecture contract suite exist. Full 34-section parity and final cross-section sign-off cannot be inferred from chapter tests; resume chapter-by-chapter. |
| 02 · #11 Integration | SUSPENDED | Baseline full 9-job matrix green on earlier commit; local document-vault changes require whole final SHA to pass again. |
| 03 · #14 Brain visualization | SUSPENDED | 3D-style volume, accessible rotate controls and recorded task state added (commits a981d9b8–a82f91e0). Full browser UX pass, true volumetric geometry and all thought-stage evidence are NOT verified. |
| 04 · #16 Project/employee title linkage | COMPLETED | Actual project, management and current task titles on graph and employees; earlier company map browser acceptance. |
| 05 · #17 Active red links | COMPLETED | `activeRouteKeys` backed by governed work and real SVG line classes, checked with a Chromium browser assertion. |
| 06 · #18 Working employee red highlight | COMPLETED | `employeeStatus`, running task state and `.map-node.employee.working` asserted in Chromium. |
| 07 · #20 Company discussions | COMPLETED | Active-human founder/department-member/direct-manager scoped employee conversations, same-channel-only replies, per-person notifications and PostgreSQL negative tests; focused CI success at 0bd57c04/e55cbd52. Project document ACL remains separate. |
| 08 · #24 CEO→CTO→PM→workers | SUSPENDED | Approved stage owner handoff exists. No signed multi-level AI delegation charter or autonomous manager execution; the reviewed project handoff stays a separate gate. |
| 09 · #26 Provisioning | SUSPENDED | Founder-mediated AI staffing and real HR roles exist. Automatic CEO-created departments or employees require reviewed revocable charter and capacity controls. |
| 10 · #27 AI task execution | SUSPENDED | Allowlisted approved AI tasks and source-controlled founder-triggered localhost batch (scripts/local_approved_agent_batch.py), single-pass no retry, offline negatives; verified focused CI e55cbd52. Multi-stage autonomous generation/real paid or local LLM delivery not demonstrated. |
| 11 · #28 Employee performance | COMPLETED | Real task/QA and workload counts; no invented productivity. Browser + PostgreSQL metrics validations exist. |
| 12 · #42 Recurring local source scanning | COMPLETED | Founder-started `market-watch`, hourly local feed scanning, dedup, health and human review gates. Laptop-off = stopped. |
| 13 · #53 AI detailed planning | SUSPENDED | Optional scoped 5-stage advisory model handler is implemented. No verified live LLM output/accepted executable plan until founder supplies budget and reviewed task. |
| 14 · #54 Reviewed team assignment | COMPLETED | Actual two-lane independent personnel approval, founder activation and immutable 058 stage ownership, idempotent PostgreSQL tests. Autonomous assignment still separate. |
| 15 · #58 Autonomous GitHub | SUSPENDED | Governed scoped GitHub adapter and CI tests exist. Real model-generated commit/PR/review loop needs an AGO-specific permissioned credential and live audited execution; ChatGPT's GitHub connection is not an AGO backend token. |
| 16 · #60 Independent artifact QA | SUSPENDED | Internal reviewer and task QA evidence exist. Complete arbitrary-artifact E2E independent acceptance is not verified. |
| 17 · #85 CEO charter | SUSPENDED | Founder sovereignty, market nomination and budgets exist. No revocable approved AI leader delegation charter allowing automatic management actions. |
| 18 · #87 Workforce analytics | COMPLETED | Backed by task state, QA evidence, workload and staffing gaps; dashboard renders real metrics. |
| 19 · #89 Self-improvement | SUSPENDED | Evidence-backed proposals/simulations only. Executed and independently reviewed model-driven optimization/rollback not shown. |
| 20 · #91 Enterprise tools | SUSPENDED | Scoped tool enrollment/authorization implemented; live external provider credentials and authorized integration tests unavailable. |
| 21 · #94 Safe failure recovery | SUSPENDED | Founder-started `company_safe_reconcile.py` dry-run/confirmation/locked stale runs; targeted negative tests pass focused CI. Real founder laptop smoke and reconciliation history remain unverified; no replay. |
| 22 · #95 Disaster recovery | SUSPENDED | Disposable isolated restore/semantic object tests exist; founder's real localhost restored-backup drill/evidence not authorized or performed here. |
| 23 · DOC-A Document permission tests | COMPLETED | Migration 059; explicit per-document founder ACL, read/grant/revoke and access audit; disposable PostgreSQL and Next.js focused CI green in run 39557767673. |
| 24 · DOC-B Confidential leak prevention | SUSPENDED | Project registry/detail/delegation/chat/event ACL; default-deny document 059; nonfounder agent run-history withheld; private project dispatch founder-only; CI tracked-file gate. Full task reports/search/tool outputs and backups/log redaction audit remain unverified; NO confidential upload. |

## Non-negotiables
- Local-first development. Founder alone controls laptop power and manually starts or stops server, scanners and optional reconciliation.
- No Railway, new cloud service, production publication, ad spend or marketing customer claims.
- An "implemented" database record does not equal live AI team execution or a published product.
- Green component CI on an older SHA does not override a red newer full matrix.
- Suspended items are *not* counted green. Resume with explicit gates, never guess external permissions.

## 21 October current execution pass
- **COMPLETED: 9 items** — #16, #17, #18, #20, #28, #42, #54, #87,
  DOC-A. These entries refer to their documented bounded outcomes, not
  production autonomy.
- **SUSPENDED: 15 items** — #2, #11, #14, #24, #26, #27, #53, #58, #60,
  #85, #89, #91, #94, #95, DOC-B.
- **No PARTIAL, IN_PROGRESS or PENDING status is accepted.** New commit's
  9-job matrix, founder laptop recovery smoke and remote authorized model/GitHub
  test are evidence gates, not implicit success.
- New local-only implementation: locked-down chat/notification visibility,
  founder-only agent run history, bounded founder-started local batch runner,
  interactive 3D-style task brain.
- **Ask founder at next applicable blocker:** choose/authorize a *local AI model
  runtime* for actual LLM execution (none was installed or invoked by GitHub CI).
  Never ask for secret API keys in chat or add cloud hosting on your own.
- Current protected branch: `develop`; current architecture/API/DB validation
  requires same-final-SHA checks. CI status must be inspected separately.

### Local Ollama founder-governed chain (2026-10-21)

- Selected `qwen2.5:3b` (1.9 GB distributed Q4) for the founder's GTX 1650
  4 GB VRAM, with `qwen2.5:1.5b` as an explicit low-memory alternative.
- Added separate bounded `company_ollama_chain` reasoning and
  `company_ollama_chain_queries` tenant-aware source-backed role lookup.
- Real identities: CEO from founder-appointed Strategy & Vision seat; CTO
  from Technology Oversight; PM from recorded project lead; employee from
  the independently approved project discovery task. Four **distinct**
  existing AI employees are mandatory.
- Opt-in `AGO_LLM_PROVIDER=ollama_local`,
  `AGO_ENABLE_LOCAL_MODELS=true`, `AGO_LOCAL_COMPANY_CHAIN=true` keeps
  previous deterministic handlers unchanged unless the founder explicitly
  enables four-role local drafting.
- Existing `POST /v1/agents/tasks/{task_id}/run` performs the task authorization
  and independent reviewer gate. New role preflight runs **before** an
  approved task is consumed. Four sequential local-only model passes create
  an actual tagged, persisted deliverable with independent QA required.
- Founder-only project inspector renders each completed role handoff from
  the durable run record; never invents background working employees.
- Ollama HTTP endpoint is fixed loopback; proxies and redirects disabled.
  No model pulling/startup, external AI fallback, tools, GitHub file writes,
  customer marketing or company mutation. One local model at a time.
- Unit plus real PostgreSQL / mocked-Ollama CI is evidence of **integration**,
  not proof of model performance on the founder's hardware.
- **Status for #24/#27/#53 remains SUSPENDED for FULL AUTONOMOUS
  MANAGEMENT/DELIVERY**; the bounded local 4-stage drafting implementation
  is done. Unbounded CTO/PM managerial authority, self-directed engineering
  execution, PR/CI and human independent QA are separate unfinished gates.
- Runbook: `docs/reports/AGO_LOCAL_OLLAMA_GOVERNED_CHAIN.md`.
