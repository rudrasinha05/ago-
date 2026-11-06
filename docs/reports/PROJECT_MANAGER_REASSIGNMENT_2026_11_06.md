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

Frontend: existing project details now include an eligible AI PM selector, an
explicit confirmation checkbox and save action carrying the expected current manager.
A successful matching response refreshes the same project and portfolio. Failed
requests remain errors; project switches discard old UI responses. No candidate
or running work produces an explicit explanation. AdmissionFlow has not been
reassigned on the owner's PC by this repository change. Issue #8 hierarchical AI approval remains a
separate feature; no human-independent approval checks are loosened here.

Validation before publication: Ruff, domain/backend/API contract guards, compile,
and 18 local unit tests passed. Eight PostgreSQL cases were skipped locally because
no disposable server was available; they must pass in CI before backend acceptance.
The real-session PostgreSQL regression checks identity/tenant/role restrictions,
no-op audit behavior and preserved project content. Existing governed chain cases
now recover legacy Founder ownership through the API and reject reassignment during
running work. Their model provider is explicitly injected test code, not real Ollama.

## Verified backend and browser follow-up
At backend commit `9a73b3e5f5917d42240350e19539b08ca5fc66d8`, Backend quality
passed 1,298 tests (run 42177571451) and focused acceptance passed 401 tests
(run 42177571507). Python 3.11 and 3.14 architecture jobs passed. Full browser
acceptance found two contrast failures on the journey refresh button in Chromium
and Firefox; 190 other browser cases passed and six were skipped. This was not an
all-green architecture run.

The contrast failure reproduced locally on the packaged app. Journey disabled/loading
buttons now use opaque, contrasting colors instead of reducing the entire control
to 45% opacity. This preserves readable labels while asynchronous refresh changes
button state. No accessibility assertions or rules were removed. The previously
failing Chromium eight-route WCAG scan passes locally after the CSS correction.
The complete CI workflow must be checked at the CSS follow-up commit as well.


The frontend manager control is covered by a browser fixture that filters human,
Board and discovery workers, requires confirmation, handles rejection then success,
and verifies no approval/run request. The real signed-session PostgreSQL Next.js
journey now checks manager selection, the durable audit row and persistence after
logout/login using actual Founder permissions (without a fabricated approval:founder
entry). Owner-PC and real Ollama acceptance remain separate.
