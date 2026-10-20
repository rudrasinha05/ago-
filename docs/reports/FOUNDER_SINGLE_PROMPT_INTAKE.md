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
