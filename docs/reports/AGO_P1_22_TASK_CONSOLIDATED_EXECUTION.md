# AGO P1 — single-batch execution register (22 unchanged gates)

## Frozen authority and meaning of acceptance

P1 remains **one governed engine** — not independently privileged employee scripts.
No P2 GitHub publication work, production deployment, cloud, payment or
automatic Windows startup was introduced. A GitHub connector's engineering
commit is not evidence that AGO independently wrote a product. Local model
simulation with test doubles is not evidence of actual GTX 1650 inference.

The canonical per-task status remains in
`docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`. This document records
actual P1 implementation changes and outstanding end-to-end evidence; it does
not silently flip the canonical release gates to Completed.

### P1 execution crosswalk

| Original gate | Existing and current implementation evidence | Still required for original full acceptance |
|---|---|---|
| #19 Meta Brain | `ago/meta_brain.py` source-backed snapshots and human-reviewed advice | Measured recommendation applied and later real comparison |
| #21 OOS | `ago/agent_runtime.py`, `ago/enterprise_store.py`, governed task queue | Multiple real assigned tasks and concurrency/recovery UAT |
| #22 AI employee state | Durable task statuses and employee status mapping; previously scoped-accepted | Periodic UAT to confirm worker state when Ollama stops |
| #23 Multi-level planning | Founder strategy, stage delegation, scoped approved tasks | Real model-created dependency graph activated with exact founder approval |
| #26 Evolution | Controlled meta recommendation and experiments, no silent mutation | Observed improvement and rollback using actual completed projects |
| #48 Genuine interactive Brain | NEW `apps/web/components/brain-3d-scene.jsx` WebGL 3D lobe mesh with depth testing, rotations, task-driven activity; SVG fallback | Device/browser GPU and accessibility acceptance |
| #58 CEO/CTO/PM/engineer hierarchy | `company_ollama_chain_queries.py` checks actual appointed identities and reporting; `run_four_role_chain` produces recorded handoffs | Distinct executed downstream subtasks, not just one bounded drafting task |
| #60 Staffing | NEW `CompanyChat.staffing_proposals`: read-only active project and AI CEO-scoped gap proposals, reuse existing specialties, no auto-hire | Revocable, founder-reviewed CEO charter and independently authorized staffing |
| #61 Multi-agent work | Seven sequential real-identity inference roles and event receipts when model enabled | Independently completed linked subtasks across multiple employees |
| #87 Model-created project plan | Opt-in `project:plan` handler; advisory-only source text | Founder validation and activated executable task graph with local model evidence |
| #119 CEO charter | Founder approval, bounded CEO reconciliation and Board assignment | Durable limited-term budgeted revocable charter with immediate stop |
| #123 Meta Brain feedback | Reflect and proposal mechanisms | Measured pre/post QA outcome improvement verified independently |
| #125 Enterprise tools | Existing allowlisted, reviewed M8 tool catalog | Employee-specific production-like authorized local invocation + isolation |
| #126 Local monitoring | `ago/local_ops.py` and signed task/activity endpoints | Actual running process heartbeat, incident recovery and local operator alarms |
| #127 Resource budgets | Virtual credit debit per model attempt, localhost model token/context bounds; NEW 60s per role/450s total chain timer | Hard measured CPU/GPU VRAM and external Ollama resource ceilings on founder hardware |
| #128 Safe failure recovery | Existing journal and fail-closed unknown execution reconciliation; previously scoped-accepted | Owner local crash drill optional for device-level release signoff |
| #135 Brain visualization | Source-backed task states + new depth-tested WebGL; no synthetic active-task lights | Live device browser audit correlating task receipts and visual routes |
| #138 Employee event popups | NEW monotonically paginated `after_id` notification stream; no 100-event client truncation, count remains durable and scoped | Extended actual-worker popup/reconnect/device acceptance |
| #139 Local Ollama seven-role chain | Already requires five distinct appointed AI Board seats + PM + task assignee; NEW per-role runtime measurements/deadlines | Seven real local inference calls and approved QA on founder Windows laptop |
| #140 Founder laptop model | NEW read-only-off-by-default `scripts/ago_p1_local_inference_probe.py` records one actual localhost inference when explicitly invoked | **Cannot be certified in GitHub CI**; founder machine must manually run and capture proof |
| #152 Continuous authorized work | Founder-confirmed `scripts/local_approved_agent_batch.py` bounded watch (max 60m/10 tasks), durable no-replay journal | Device-level multiple approved task runs, real worker incidents and resource limits |
| #154 Interrupted recovery | Existing no-replay, stale-run and safe manual reconciliation; previously scoped-accepted | Owner-local crash recovery drill optional for actual laptop |

All 22 gates retain their original numbers and definition; these are
**implementation pointers, not assertions that each full acceptance passed**.
The known completed scoped baseline before this batch is #22, #128 and #154.
Any additional Completed claim requires the associated full release evidence.

## Measurable new P1 changes

1. Seven-role internal model chain now checks each inference <=60s and total
   <=450s, while preserving virtual credit charges, per-identity recorded
   events, independent QA and founder-only task approval.
2. The WebGL brain is actual 3D geometry with depth testing and pointer/
   button rotation. Its active color and accessible count depend on signed
   task rows. When WebGL is unavailable the existing SVG observatory remains.
3. Founder-controlled Ollama probe defaults to dry-run, supports no model
   download/service start or remote endpoint, never copies prompts/results to
   disk and reports response hash + timing only after one confirmed local call.
4. Notifications use an after-ID cursor and ascending pages of at most
   100, so the browser can drain a large backlog without dropping queued
   event notifications. Server-side role/tenant filtering still applies.
5. CEO-backed staffing recommendations only read *active founder-owned*
   projects with an actual appointed AI CEO. No AI hire, permissions,
   constitutional delegation, spending or new staff record is created.

## Operator-only localhost verification (not run by CI)

From the existing repo root on Windows, using the **already-installed** model
and a manually started localhost Ollama server:

```powershell
ollama list
ollama ps
python scripts/ago_p1_local_inference_probe.py --model qwen2.5-coder:1.5b
python scripts/ago_p1_local_inference_probe.py --model qwen2.5-coder:1.5b --confirm-live
```

The first Python invocation is a no-network dry-run; the second explicitly
performs one inference on `127.0.0.1:11434` only. The probe verifies that
Ollama returned a completed model output, **not** model quality, GPU offload,
independent QA, external tool use or autonomous company operation.
Never paste founder passwords, real private briefs or GitHub tokens into the probe.

After separate Founder-approved tasks exist, the previously reviewed
`./scripts/ago.ps1 serve` and `scripts/local_approved_agent_batch.py`
can be explicitly started in one terminal session. Its watch mode never
registers a startup service or replays unknown task outcomes.

## Final P1 stop gate

Do not mark P1 22/22 or start P2 based only on GitHub green checks.
Owner-local inference, durable CEO charter, independent real-subtask QA,
incident/resource measurement and full live acceptance still require actual
evidence. Source-level regression and signed simulated-PostgreSQL browser
checks are narrower guarantees than the requested autonomous company.
