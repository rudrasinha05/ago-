# Advance project: AGO moves a project forward by itself (self-sufficiency step)

Implemented by Claude on 2026-11-07 (JARVIS away; the Founder asked Claude to carry the work).

## What the Founder sees
Each active project in the Delivery Journey has an **"Let AGO move this project forward"** panel:
- **Show next step** says, in plain language, what AGO would do next.
- The Founder ticks **"Allow AGO to do these steps and use internal AI credits"**. The tick is cleared after every use.
- **Do the next step** performs one step. **Keep going until I am needed** performs steps until a person must act, up to 12 steps per press. **Stop after this step** is available while it works.
- A live, timestamped log lists every step and its recorded result: who approved, the self-check outcome, the run result and the QA verdict.

## How AGO decides the step (`project-advance-state.js`)
It looks at the first stage, by position, that has not passed QA. Steps AGO does itself:

| Stage state | AGO does | Existing endpoint |
|---|---|---|
| task `proposed` | ask for approval | `POST /v1/console/tasks/{id}/request-approval` |
| `waiting_approval`, approval pending | get the AI team approval: direct manager → project manager → CEO (M2) | `POST …/projects/{id}/ceo/reconcile` |
| `waiting_approval`, approved | run the self-check (preflight plus credit balance) and, only if it passes, run the AI team | `GET /v1/agents/tasks/{id}/engineering-preflight`, `GET /v1/insights/scorecard`, `POST /v1/agents/tasks/{id}/run` |
| `completed` run, no QA | an independent AI QA check, by a QA-role AI who is not the stage worker | `POST …/stages/{stage}/ai-qa` (M4) |

AGO stops and tells the Founder when:
- the stage needs **rework** after a QA FAIL;
- the task **failed** (use recovery);
- the approval was **rejected**;
- the task is **running**;
- the stage is **unstaffed**;
- the state is **unknown**;
- every stage is **done**.

AGO also stops when:
- the AI team could not approve the task (the Founder decides in Approvals);
- the self-check shows blockers;
- the run does not complete;
- there is no eligible QA reviewer;
- the QA verdict is FAIL or unclear;
- any request errors.

## Authority
The page only chooses which existing endpoint to call next. Every server check still applies: signed Founder session, approvals and hierarchy, self-check, credits at run time, the independence of the QA reviewer, and the one-run-per-task rule. Nothing is committed, released or published.

## Backend change
`GET /v1/organization/company/projects/{id}` now returns `task_approval_status` for each stage (from the task's approval request), so AGO can tell a pending approval from an approved one.

## UI detail
Only a page change clears the Delivery Journey cards. Any refresh (manual, timer or a parent signal) keeps them mounted, so a running Advance log or an open form is never wiped. This fixed an intermittent WebKit failure where a parent refresh unmounted the panel mid-run.

## Tests
- **Unit** (`scripts/test_founder_delivery_journey.mjs`): every step kind, ordering by position, skipping passed stages, labels, and that the QA reviewer is never the stage worker.
- **Playwright**, on all 6 projects:
  - one stage goes through request → AI team approval → self-check → run → AI QA to done; the builder, even with a QA role, is not chosen as QA; the tick is cleared afterwards;
  - a self-check blocker (Board incomplete, 0 credits) stops before any run.
- **Backend:** `task_approval_status` goes from pending to approved, in `test_hierarchy_task_approval.py`.

## Next
- A server-side scheduled "advance", so the Founder does not have to keep the page open, still bounded by the same checks and a Founder-set credit allowance.
- Later stages (architecture, implementation, release) are still bounded by the existing engineering and release gates.
