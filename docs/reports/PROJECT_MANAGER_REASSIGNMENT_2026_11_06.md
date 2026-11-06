# Existing project manager recovery — Issue #9

Backend contract: `POST /v1/organization/company/projects/{project_id}/accountable-manager`.
Signed active project Founder only; requires `organization:read` and server-derived
`approval:founder`. Body: `{ "employee_id": "UUID", "expected_manager_id": "UUID" }`.
`expected_manager_id` is optional for compatibility; UI should supply the currently
visible manager to detect stale selections. The endpoint returns existing project
details, now including `accountable_manager_role`, `assigned_at`, and
`manager_change: {changed, previous_manager_id, manager_id}`.

The target must be an existing same-tenant AI employee with an intake-allowlisted
PM role and report directly to the appointed AI CEO. Board members and project
workers are excluded: suggested discovery/implementation/quality workers,
all activated stage workers and actual task assignees. A nonactivated release
preparation suggestion alone does not prevent a delivery manager assignment.
Employees currently have no active/inactive flag; existence in the current employee
registry is the available employee lifecycle check. Founder user activation is checked.

Reassignment locks existing plan tasks in runtime admission order, then project
ownership. Runtime admission shares the project lock so a newly materialized
task also cannot race the assignment change. Running tasks or agent runs block an actual change. Repeating the same
valid manager is a no-op. Unknown/nonowned projects return 404, unauthorized users
403, invalid/stale targets or running work 400, malformed inputs 422.

Migration 067 allows `founder_reassignment` and records each actual change through
a database trigger in append-only `ago_project_manager_changes`, including previous
and new manager, signed actor and timestamp. No plan, task, approval, role,
reporting line, model run or QA result is created/approved/changed. Existing approvals
retain their original action and assignee. Runtime still rechecks current hierarchy;
a worker outside the new PM's reporting line needs the separate reporting repair.

Frontend handoff: preserve the existing project, select an eligible AI PM, submit
with expected manager, then refresh details and self-check. This patch does not
claim that Claude's manager-selection screen is implemented or that AdmissionFlow
has been reassigned on the owner's PC. Issue #8 hierarchical AI approval remains a
separate feature; no human-independent approval checks are loosened here.

Validation before publication: Ruff, domain/backend/API contract guards, compile,
and 18 local unit tests passed. Eight PostgreSQL cases were skipped locally because
no disposable server was available; they must pass in CI before backend acceptance.
The real-session PostgreSQL regression checks identity/tenant/role restrictions,
no-op audit behavior and preserved project content. Existing governed chain cases
now recover legacy Founder ownership through the API and reject reassignment during
running work. Their model provider is explicitly injected test code, not real Ollama.
