# AI Board on live runs, and the Founder override of a Board denial

Implemented by Claude on 2026-11-07. JARVIS is away; the Founder asked Claude to carry the work. JARVIS should review on return.

## What the live runs on the Founder PC showed
The project is AdmissionFlow and the stage is discovery. The full five-seat Board, PM and worker run through local Ollama.

| Run | Model | Result | Cause → fix |
|---|---|---|---|
| 1 | qwen2.5-coder:1.5b | CEO wrote `DECISION: APPROVE`; no vote line; unverified; Board stop | The vote line was asked for after the headings → `9dfdffa`: the vote line comes first |
| 2 | 1.5b | CEO wrote `DECISION: DENY` | The model follows the heading list → `3b0c74c`: the Board heading list carries the vote |
| 3 | 1.5b | CEO gave a verified `DENY` with no reason | Model capacity → the Founder chose `qwen2.5:3b` |
| 4 | qwen2.5:3b | CEO APPROVE with a real deliverable and risks; CTO wrote `### BOARD_RECOMMENDATION` / `DENY` | Heading-form vote → `798d9db`: that form is now parsed (still exactly one vote) |
| 5 | 3b | CEO APPROVE, CTO APPROVE, CFO verified **DENY**, copying the same draft with no finance reason | See the Founder rule below |

Credits used: 8 of 30. Every run went through the full path: approval request, AI hierarchy approval (the Strategy Manager as the direct manager), self-check, then the model run.

## Founder rule (stated 2026-11-07, chat)
> if CEO and CTO have approved then ask for denial with other board members, and display to the founder the reason for denial and who denied? if founder approve or allow the project then it must be completed. assign task to the dedicated employee… if role is not assigned then it is task of board members to assign role to their employee

## Implemented
- **Deny reasons.** The Board prompt asks a DENY to give `DENY_REASON: <one sentence about YOUR seat's area>` and asks each seat to review the work itself rather than copy the previous draft.
  - `denial_reason()` keeps exactly one such line, up to 300 characters.
  - Each `board_recommendations` entry now has `denial_reason` and `founder_override`.
- **Override availability.** When the stopping seat is Finance, Risk or Quality and both CEO and CTO approved in that run, the result has `founder_override_available: true`.
- **New endpoint:** `POST /v1/organization/company/projects/{id}/stages/{stage}/board-override`, with body `{failed_task_id, seat, reason}`.
  - The signed project Founder only; `seat` must be one of the three Finance, Risk or Quality seats (otherwise 422).
  - The stage must still be linked to the failed task.
  - The run must be Board-blocked by exactly that seat, with a `deny` or `unverified` vote.
  - CEO and CTO must have approved in that run.
- **On success:**
  - one immutable row in `ago_board_founder_overrides` (migration `073`), holding the seat, the denial vote and reason, the Founder and the Founder's reason; unique per project and seat;
  - an ordinary audited stage recovery: a new proposed task that needs its own approval. Nothing is run.
- **Later runs in that project:** a non-approve vote from an allowed seat is recorded with `founder_override: true` and listed in `founder_overrides_applied`, and the AI team continues.
  - This applies only after CEO and CTO approved in the same run.
  - CEO and CTO denials are never overridable.
  - `board_review_cleared` stays false: a DENY is never reported as a clean Board pass.
- **UI:**
  - On a stage stopped by the Board, the Founder sees every seat's vote, the reason or "No reason was given", and who stopped it.
  - When allowed, there is a "Founder: allow the project anyway" button with a reason and a confirmation.
  - Advance says when the Founder can allow, and quotes the reason given.

## Tests
- `test_board_recommendation_parse.py`, over a full five-seat Board:
  - a Finance DENY is offered to the Founder;
  - an allowed seat lets all 7 roles complete;
  - a CTO denial or unclear vote is never overridden;
  - the deny-reason parsing.
- `test_board_founder_override.py` (PostgreSQL, signed sessions):
  - the 401/403/404/422/400 matrix;
  - the override row and the new proposed task;
  - project-scoped seats;
  - immutability;
  - no override when the CTO stopped the run.
- Unit tests for `boardDenial` and `runBlocker`; Playwright on all 6 projects.

## Not done yet
- **"If a role is not assigned, the Board assigns it to their employee."** AdmissionFlow's quality stage has no employee. That needs the Board (CEO/CTO) to staff an unstaffed stage with a matching AI employee. A stage without a plan step cannot be added to an active plan today (the `ago_guard_plan_step` rule). This is the next item.

## Deny → revise → resubmit (Founder: "deny ek end nhi h")
Run 6 on the Founder PC: the Founder allowed the Finance seat, and then the AI CEO denied with a real reason: "brief lacks specific problem-solving capabilities…". The Founder asked that a denial be resolved, improved and resubmitted, because that is the workflow.

- **Backend:** `CompanyOllamaChainQueries.revision_notes(task)` reads the audited recovery link and the replaced task's recorded Board votes, giving each non-approving seat and its `denial_reason`, plus the recovery note, up to 700 characters.
  - The chain adds a `REVISION:` block to every role's prompt: the Board feedback as quoted data, "fix each point explicitly and say how; do not repeat the denied approach".
  - The brief and the notes are shortened so the prompt stays within the 4000-character limit.
  - The result has `revision_of_denied_attempt`.
- **Advance:** a Board stop (the task failed but its AI run completed, with no failure code) is the step `revise`. AGO creates the audited recovery task, with the reason "Revise to fix Board feedback: <seat>: <reason>…", and continues: request → hierarchy approval → run → QA.
  - At most 2 revisions per press; after that AGO stops and shows the Board feedback.
  - Crash, timeout and credit failures still stop for the Founder.
- **Tests:**
  - every role's prompt carries the feedback and stays within 4000 characters, and a first attempt has no feedback;
  - PostgreSQL: `revision_notes` after an override recovery;
  - unit tests for the step kinds and the reason text;
  - Playwright: DENY → revise → request → approve → run → QA PASS → done.

## The project manager rewrites the scope before the Board sees it again (live run 7)
Credit allowance was set to 1,000,000 at the Founder's request. Advance revised twice and the CEO denied both times with the same reason. Cause: the CEO is the first role, so it always judged the original brief; the team's revision never reached it.

The fix, when `revision_notes` is present:
1. The project's AI manager (`pm` participant) first writes an IMPROVED scope. This is one bounded model call, metered as one credit. Its headings are PROBLEM, USERS, FIRST_VERSION, OUT_OF_SCOPE, SUCCESS_MEASURES and HOW_FEEDBACK_IS_FIXED.
2. That scope is the "previous draft" the CEO and every later role judge. The REVISION block tells them to judge the improved scope, not only the original brief.
3. The result records `revised_scope`, the PM's draft. `roles_completed` still counts the 7 chain roles.

Advance logs "<PM> (project manager) rewrote the scope…".

## Missing vote follow-up (live run 8)
The PM wrote a real improved scope: problem, users and a first version for universities and admissions teams. The AI CEO then copied that scope's format and wrote no vote line, so the vote was unverified. On the second revision the feedback degraded to "denied without a stated reason".

Fixes:
- **Missing-vote follow-up**, full Board only. When a seat's draft contains no BOARD_RECOMMENDATION at all, the same seat gets one short vote question (metered, bounded). A clear reply is prepended to the persisted draft, so the vote is stored with the evidence. A draft with conflicting votes is not asked again and stays unverified. The legacy two-seat mode is unchanged.
- **Prompt:** Board prompts end with a reminder to start with the vote line and not to copy the previous draft's format.
- **Feedback is carried forward:** `revision_notes` labels an unclear vote as "gave no clear vote". When the latest attempt has no stated reason, it appends the earlier recovery's feedback ("Earlier feedback: …").

## Run 9: the full Board approved; the code proposal failed its check
In revision 2, after the PM rewrote the scope following the CTO's feedback, all five Board seats approved and the PM role completed. The engineering worker's JSON then failed AGO's static code check. That raised a plain ValueError, which was recorded as `handler_error` ("unclassified").

Fixes:
- **Self-correction.** The same developer is told which of AGO's fixed check messages failed (AGO's own text, never model text) and gets one corrected answer. A second failure raises `EngineeringCandidateInvalid`, with failure code `engineering_candidate_invalid`. It is added to `RUN_FAILURE_CODES`, to the preflight mirror, to `local_approved_agent_batch`, and to the UI reason. Nothing is executed.
- **Advance.** `engineering_candidate_invalid` becomes the automatic step `retry_code`: an audited recovery, counted within the 2-attempt limit.
- **Bug fix.** `revision_notes` returns '' unless the replaced run was a Board stop. A crash, timeout, credit or code-check recovery no longer triggers the PM scope rewrite.
