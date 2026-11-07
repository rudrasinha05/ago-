# Independent AI QA of a finished stage — Issue #8 M4

Implemented by Claude on 2026-11-07, at the Founder's instruction. JARVIS should review it.

## Why
The Founder's rule: the Founder is the only human in AGO, and everyone else is an AI employee. `QualityStore.review` requires `kind='human'`, so every stage QA had to wait for the Founder, and no stage could finish through the AI organization. This change is additive. The human QA path (`/v1/.../review`, `QualityStore.review`) is unchanged.

## Backend contract
`POST /v1/organization/company/projects/{project_id}/stages/{stage}/ai-qa`

- **Who may call it:** the signed project Founder only. The route requires `organization:read` and `approval:founder`, the role `founder`, and `founder_id` equal to the caller. This is the same authority as stage recovery.
- **Body:** `StageAiQaInput {qa_employee_id: UUID, operation_key: UUID}`. The schema is strict; extra fields return 422.
- **Eligibility.** The check runs in a transaction before the model call, and again after it:
  - the plan is active;
  - the stage's linked task is `completed`, its single agent run is `completed`, and there is no `ago_task_reviews` row yet;
  - the QA employee exists, is `kind='ai'` and is not terminated (`ago_personnel_events`);
  - the QA employee's `role_title` matches `qa|quality|test(er|ing)`;
  - **independence:** the QA employee is not the task assignee, not the run's agent, and not any `employee_id` in the run's `result.handoffs`.
- **Model:** the same opt-in local Ollama gates as the chain (`AGO_LLM_PROVIDER=ollama_local`, `AGO_ENABLE_LOCAL_MODELS=true`, `AGO_LLM_MODEL`). If those are not set, the call returns 403 and no credit is charged.
- **Credit:** 1 virtual credit is charged before the call, with the key `ai-qa:{task}:{operation_key}`. Re-sending the same key returns 400; it is not a free retry. A model failure still costs the attempt and returns 502.
- **Verdict:** the response must contain exactly one `QA_VERDICT: PASS|FAIL` line, otherwise the verdict is `unverified`.
- **Writes, in one transaction:**
  - always, an append-only `ago_ai_qa_reviews` receipt: model, prompt and response sha256, the bounded response (≤4000 chars), the verdict and the credit usage id;
  - for PASS or FAIL only, the ordinary `ago_task_reviews` row via the new `QualityStore.record_ai_review`, with `reviewer_id` = the AI QA employee and `author_id` = the task assignee. `quality_store` stays the only writer of `ago_task_reviews`. The existing 049 trigger notifies both employees.
- **Result:** `{kind:"ago_ai_qa_review_v1", verdict, review_recorded, receipt_id, qa_employee_name, model, response_text, credits_charged:1, executed_or_released:false, ...}`.
- **Never** runs, commits, releases or approves anything.

## Migration `069_ai_qa_reviews.sql`
- **New table** `ago_ai_qa_reviews`:
  - `CHECK (qa_employee_id <> author_id)`;
  - a partial unique index, so there is one `pass`/`fail` row per task;
  - an append-only trigger.

## Code
| Change | Where |
|---|---|
| Service, pure helpers (`qa_verdict`, `builder_ids`, `deliverable_text`, `qa_prompt`) and `local_qa_provider()`, a test seam | `ai_qa_review.AiQaReview` (governance/service) |
| SQL methods 01–03 | `ai_qa_review_queries.AiQaReviewQueries` (governance/persistence) |
| AI reviewer method | `QualityStore.record_ai_review` |
| New ports | `AiQaReviewPort`, `AiQaReviewQueriesPort` |
| QualityStorePort | adds `record_ai_review` |
| Route | `api_company_chat.ai_qa_stage` |

**Contract registers:**
- `architecture_policy.json`: 2 nodes, plus the `repository_ports` imports.
- section03: modules and `sql_access`.
- section05: components.
- section13: the operation and schema.

## Frontend
In the Delivery Journey, a stage that is completed, has a completed run and has no QA shows "Ask AI QA to check":
- The Founder chooses an AI QA-role employee, ticks a confirmation box and runs the check.
- The result (verdict, reviewer and receipt) appears as a notice, and the stage then refreshes to `QA: pass/fail`.
- The "Independent QA required" guidance now points to AI QA.

## Tests
- `tests/test_ai_qa_review.py`, PostgreSQL with real signed sessions, covers:
  - the 401/403/404/422 matrix;
  - a non-QA role, the builder and an unknown employee are refused before any model call;
  - a PASS creates a review and a receipt and uses 1 credit, and the stage shows `qa_verdict=pass`;
  - no second verdict, and receipts are immutable;
  - an ambiguous answer creates a receipt with no review, the same key is refused, and a new request can record FAIL;
  - with no model configured the call returns 403, a model timeout returns 502, and an unstaffed stage returns 404.
- `scripts/test_founder_delivery_journey.mjs`: `aiQaReadyStage` and `aiQaReviewers`.
- Playwright: the Founder chooses Quinn (QA Engineer) and the non-QA writer is not offered; exactly one POST; the PASS notice; `QA: pass`; axe. All 6 projects pass.

## Not done / next
- Choosing the QA reviewer is a Founder action for now. M2/M5 should let the AI CEO or the project's QA lead request it within the hierarchy, and later do it automatically when a stage finishes.
- A FAIL verdict on a *completed* task has no follow-up path yet. Stage recovery only accepts `failed` tasks. Next: a "rework" task after a QA fail.
- AI QA reviews the recorded drafts. It does not execute code. Docker/test evidence stays a separate gate.
