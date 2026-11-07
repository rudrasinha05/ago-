# Hierarchical AI approval of project tasks — Issue #8 M2

Implemented by Claude on 2026-11-07. JARVIS is away; the Founder asked Claude to carry the backend too. JARVIS should review it on return.

## Founder rule
The Founder is the only human. Company-level (major) approvals go to the Founder. Project work is approved by AI agents **by hierarchy**: a manager or senior employee may approve small work, and is then responsible for it.

## What changed
Before this change, every in-scope project task approval in `ceo_reconcile` was recorded under the AI CEO. Now `ApprovalRepository.approve_project_task_by_hierarchy` picks the approver itself (governance-owned; the client never names an approver).

It tries these levels in order and uses the first one that qualifies:
1. **direct manager**: `ago_governed_tasks.accountable_manager_id`, set from the worker's `manager_id` on task insert (migration 052);
2. **project manager**: `ago_founder_project_lead.accountable_manager_id`;
3. **AI CEO**: the `Strategy & Vision` board seat.

An approver must exist, be `kind='ai'`, have no `terminated` personnel event, and not be the worker. Any level that is skipped is recorded with its reason: `not assigned`, `not found`, `is the worker`, `not an AI employee` or `no longer employed`. If no level qualifies, the task stays blocked for the Founder; the reconcile result lists it in `blocked_task_ids`.

The scope checks are exactly the ones in the CEO path:
- the plan is active;
- the Founder approved the plan;
- the task is `waiting_approval`, with an exact action match;
- only these actions are allowed: `internal:brief`, `research:brief`, `project:plan`.

## Records
- `ago_approval_requests.reviewer_id` is set to the chosen approver.
- The approval `reason` states the approver and level, says they are "responsible for this decision", lists the levels "escalated past", and gives the Founder session.
- `ago_approval_audit.actor_id` is set to the approver.
- **New** append-only table `ago_hierarchy_task_approvals` (migration 071): approval, task, project, approver, `approver_level`, worker, `skipped` jsonb and Founder session. It has `CHECK(approver_id <> worker_id)` and one row per approval.

## API
- `POST /v1/organization/company/projects/{id}/ceo/reconcile` keeps its route and authority. Its result adds `task_approvers: [{task_id, approver_id, approver_name, approver_level}]`.
- Approval inbox: `decided_by_level` for a project task is now `ai_hierarchy`, and `review_routing` explains the order: manager → project manager → AI CEO.
- Stage staffing (`approve_ceo_project_stage`) is unchanged. The CEO still affirms only Founder-approved staffing.

## UI
- The project button now reads "Get AI team approvals (manager → project manager → CEO)". Its notice names each approver and level, and says how many tasks wait for the Founder.
- The same notice appears after the Founder's one-time scope decision.
- The approvals banner explains the hierarchy.

## Tests
- `tests/test_hierarchy_task_approval.py` (PostgreSQL, signed sessions):
  - a direct AI manager approves, and the reviewer, audit actor and record are all that manager;
  - a human manager is skipped and the project manager approves;
  - when both the manager and the project manager are the worker, the AI CEO approves;
  - a manager terminated through the governed HR flow is skipped;
  - the record is immutable.
- The existing CEO, stage and dual-approval suites pass unchanged.
- `scripts/test_founder_delivery_journey.mjs` tests `hierarchyApprovalLine`.

## Not done / next
- **Approval limits** (for example, a manager may approve only `internal:brief`, and bigger actions need the PM or CEO): there is one allow-list today. Per-level limits need a Founder-approved matrix (M3).
- **Automatic progress:** the hierarchy approval still starts when the Founder presses the button. Next, a stage finishing should request the next stage's approval and the AI QA automatically, still with no model run without a recorded approval.
