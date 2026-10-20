# Founder single-prompt intake — governed draft milestone

The founder enters one brief on the Company Map. The authenticated tenant-scoped
`POST /v1/organization/company/projects/start` endpoint atomically creates:

- one real M3 goal with the exact founder brief;
- one M3 draft plan linked to that goal;
- five stored draft deliverable stages: discovery, architecture, implementation, independent QA, release;
- grounded suggested assignees using only real same-tenant employees/approved reviewer roles; absent roles show staffing gaps;
- **at most one** allowlisted `internal:brief` M3 draft step for an existing AI employee (no external actions);
- a durable founder project event and a read-only project list.

Requests use founder permissions, a UUID operation key and a digest-bound
retry guarantee. A retry with changed text is rejected; a cross-tenant read
reveals no other company's briefs. Stages are proposed deliverables, **not**
completed tasks, committed code, published documentation, or automatic agent
execution. The plan remains `draft`; existing independent human approval,
per-task approval, QA and the reviewed Section34 GitHub operation workflow are
unchanged. Final release decisions still belong to the founder.

The title is the first line of the user brief (up to 220 characters), not an
LLM guess. This is deterministic decomposition, not an agent that can
independently build any requested software. Before attempting any such claim,
verify project-specific developer tools, deployment credentials, budgets,
independent QA, GitHub rights and a real end-to-end test.

Acceptance: `apps/backend/tests/test_company_chat.py`, current HEAD
CI (Python 3.11/3.14, PostgreSQL, Next.js build and browser) and migration
`051_founder_project_intake.sql`.

## Explicit approved scope-packet execution
When a staffed discovery step receives **two separate gates** (independent
approval of its M3 plan, followed by M2 approval of the materialized task),
the existing allowlisted `internal:brief` agent can execute. The M4 runtime
now reads the original intake **only through the exact tenant-scoped plan
step/task ID join** and supplies it as bounded non-executable context.
The deterministic handler returns a founder-specific scope review packet,
flags unverified engineering and GitHub claims as false, persists a real run
record and triggers ordinary employee manager reporting. It does not use
a paid model, generate application code or perform any network operations.
Unrelated `internal:brief` tasks retain their original generic result.

## Approval Inbox UX — real authorization retained
The Company Map shows a tenant-scoped approvals inbox. It reads actual stored
requester, plan/task IDs, immutable action and status, actual reviewer decision,
and optionally a bounded stored founder brief. It never assigns a fictional
approver or treats a board title as a role grant. Approve/Deny, with a mandatory
reason, goes through the original /v1/governance/approvals/{id}/decision.
Founders cannot self-review their own project approval. User-visible
request updates are polled only while the authenticated page is open, not
system notifications when the browser or laptop is closed. The founder brief
remains addressed to Company Brain, not automatically forwarded to CEO/CTO.

## Manager accountability / commercial objective milestone (52)
A new project has a mandatory, same-tenant, recorded executive responsible
for delivery and commercial validation. Recognized actual CEO, COO, CTO,
director, or management role is preferred. If the company has none, the
authenticated human founder is the recorded *escalation owner*, explicitly
showing a leadership staffing gap. Workers may be assigned discovery or
engineering steps but do not own overall delivery.

Every existing and newly inserted M2 governed task has a same-tenant
`accountable_manager_id`: its assignee's actual manager or, for an
unmanaged/root worker, the active human founder. A database trigger enforces
this independently of API writers and backfills old tasks, without changing
their authorizations. Existing founder projects are conservatively backfilled
to founder escalation rather than retroactively inventing an AI CEO.

A project commercial goal says "find paying customers", but actual revenue
is deliberately NULL until verifiable evidence exists. This milestone does
not create sales, customers, budgets or cashflow. The manager workload page
counts only real governed tasks; no artificial assignments or round-the-clock
activity is generated. A full dynamic CEO→CTO→PM execution orchestrator,
commercial sales funnel, verified invoice/transaction ingestion and broader
action ledger across all other subsystems remain backlog items.

### Compatibility exception with visible escalation
Some historical and integration-test tenants never had a real management
hierarchy or an active human founder. The 052 migration deliberately does
not fabricate a supervisor or break all existing governed tasks in those
tenants: their executor remains the accountable identity with
`management_escalation_required=true`. The management dashboard displays
these pending leadership assignments. Newly created founder projects still
require a real founder employee and a named executive owner or founder
escalation. This is not universal enforcement across every enterprise tool.
