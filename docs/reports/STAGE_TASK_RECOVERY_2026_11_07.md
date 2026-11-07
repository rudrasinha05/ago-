# Failed stage recovery, credit preflight and safe failure codes — Issue #10

Implemented by Claude on 2026-11-07, while JARVIS was out of capacity, at the Founder's explicit instruction. JARVIS should review it.

## Live trigger (Founder's PC)
AdmissionFlow discovery reached "Self-check passed", then `POST /v1/agents/tasks/f0f990f6…/run` returned 502 after about 10 s. The run was stored as `handler_error`.

`GET /v1/insights/scorecard` showed `virtual_credit_budget = 0/0/0` and `handoffs = 0`. The first metered model call raised before Ollama was contacted. Ollama itself was healthy (`/api/tags` listed `qwen2.5-coder:1.5b`).

The task was then permanently `failed`, for two reasons:
- `ago_agent_runs` is `UNIQUE(tenant_id,task_id)`.
- `ago_guard_plan_step` forbids relinking a step.

Nothing implemented the "obtain a new authorized recovery" path that the UI promised.

## Backend contract
`POST /v1/organization/company/projects/{project_id}/stages/{stage}/recovery`

- **Who may call it:** the signed project Founder. The route requires `organization:read` and server-derived `approval:founder`, the role `founder`, and `founder_id` equal to the caller.
- **Body:** `StageRecoveryInput {failed_task_id: UUID, reason: str 1..500}`. The schema is strict; extra fields return 422.
- **Behaviour:** in one transaction it locks the stage's plan step and the failed task. It requires all of the following:
  - the plan is active;
  - the step is still linked to `failed_task_id`, otherwise 400 (stale);
  - the task is `failed` with no running run;
  - the task has not already been recovered;
  - the task's action and assignee equal the step's.
- **Effect:** it creates a NEW `proposed` task with the step's action and assignee through `TaskStore.propose`. It inserts an append-only `ago_plan_step_task_recoveries` row (actor, reason, time) and relinks the step.
- **Result:** `{kind: "ago_stage_task_recovery_v1", recovery_task_id, recovery_task_status: "proposed", approval_required: true, run_started: false, ...}`.
- **Never** approves, runs or replays anything. The new task uses the ordinary `/v1/tasks/{id}/approval` flow, and the failed task and its run stay as evidence.
- **Errors:** 401 unsigned, 403 non-Founder, 404 for an unknown project or a stage without a plan step, 400 for stale, not failed, already recovered or mismatched, 422 for malformed input.

Code: `PlanExecution.recover_failed_stage` (service), `PlanExecutionQueries` methods 07–10, `PlanExecutionPort`, and `api_company_chat.recover_failed_stage`.

## Migration `068_plan_step_task_recovery.sql`
- **New table** `ago_plan_step_task_recoveries`. It is append-only (`ago_protect_append_only`), with `UNIQUE(failed_task_id)` and `UNIQUE(recovery_task_id)` and tenant-scoped FKs.
- **`ago_guard_plan_step` replaced.** The original rules are unchanged. One extra transition is allowed, on an active plan only, when every one of these holds:
  - the old task is `failed` and has no running run;
  - the new task is `proposed` with the same action and assignee;
  - a matching recovery row exists;
  - every other step column is unchanged.

  Anything else still raises "Approved plans cannot be edited". The PostgreSQL tests cover both a direct SQL relink without a recovery row and an audit-row update.

## Safe failure codes
- `credit_domain.CreditBudgetMissing` and `CreditBudgetExceeded` are `PermissionError` subclasses, so existing callers keep working. `credits.py` raises them.
- `agent_runtime.run_failure_code(exc)` classifies by exception type only, walking `__cause__` and `__context__`. The possible codes are:
  - `credit_budget_missing`, `credit_budget_exceeded`
  - `model_timeout`, `model_unreachable`, `model_incomplete`
  - `handler_error` otherwise

  Exception text is never stored.
- The preflight and `scripts/local_approved_agent_batch.py` accept these codes. The preflight mirrors the list because module policy forbids importing `agent_runtime`.

## Preflight
`inspect_engineering_task` now reads `ago_credit_budgets` (read-only, SELECT only). It reports `credits_required` (one per chain role) and `credits_remaining`. When `remaining < required` it adds `virtual_credit_budget_insufficient`. The run-time gate list is unchanged, because credits are still re-checked at Run.

## Reviewed contract updates
- `section05_backend_contracts.json`: new `PlanExecution` and `PlanExecutionQueries` methods.
- `section13_api_contract.json`: the new operation and the `StageRecoveryInput` schema.
- `section03_domain_contracts.json` `sql_access`:
  - `company_engineering_preflight` now reads `ago_credit_budgets`, a read-only cross-context read for diagnosis.
  - `plan_execution_queries` now reads the founder intake, stage, task and run tables plus the new recovery table.

There are no module-policy import changes.

## Frontend
- **Delivery Journey:** failed stages say why they failed in plain language. "Recover failed stage" asks for a reason and an explicit confirmation, calls the endpoint, then refreshes and points to the Execution Desk to request approval.
- **Execution Desk:** the AI credit allowance panel (from `85e62c2`), and the self-check blocks when credits are low.

## Tests
- PostgreSQL, real signed sessions (`tests/test_stage_task_recovery.py`): the failure produces `credit_budget_missing`; the full 401/403/404/400/422 matrix; a successful recovery; the audit row; failed evidence unchanged; no second recovery; the new task enters approval; the database refuses an unaudited relink and an audit rewrite.
- Unit: `tests/test_run_failure_codes.py`, plus credit and failure-code cases in `tests/test_company_engineering_preflight.py`.
- Full backend suite: 1,316 passed before the `sql_access` register update; the remaining failure was that register, fixed afterwards.
- Playwright: the recovery flow on all 6 projects, with no run or decision requests.

## Not done / remaining
- The recovery on the Founder's PC requires pulling, migration 068 and setting the credit allowance. It is not yet executed there.
- Issue #8 (hierarchical approvals) is not started.
