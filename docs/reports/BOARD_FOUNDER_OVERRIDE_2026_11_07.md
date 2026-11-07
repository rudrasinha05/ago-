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
