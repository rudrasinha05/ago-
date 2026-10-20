# Founder company map and conversation workspace

Scope: the Organization workspace now opens a founder-centred, pannable and zoomable company map, with a central composer, department/employee hierarchy sidebar and a persistent organization timeline. Existing administrative forms remain under Advanced organization controls.

## Implemented

- Existing employees and actual manager IDs determine reporting edges; root employees connect to the founder. Department nodes group the company without inventing executive appointments.
- Select an employee to inspect assigned tasks, recorded task state and the linked strategy plan. Unlinked tasks are explicitly labelled.
- Idle is green; a recorded running task is red/busy; pending work is amber; unavailable activity is grey/unknown. Idle is not a claim of model connectivity or online presence.
- Chat channels cover global, departments and employees, with chronological history, reply references, older-page loading, preserved message whitespace and idempotent send retries. These are tenant-visible channels, not private direct messages.
- Continuous history uses database pagination; individual messages are bounded to 20,000 characters.
- Migration 048 records new task status transitions transactionally, independently of whether a browser is open. Existing tasks receive explicitly labelled initial snapshots rather than invented past transitions.
- Status changes are polled every seven seconds and shown as dismissible popups. Chat polls every five seconds.
- Add needed role requires an explicit requirement, department and optional same-department manager. The authenticated organization manager creates an AI profile; duplicate names and altered retry requests are rejected. Its requirement is saved in the timeline. It grants no model or execution authority.
- Authentication, tenant grants, organization constitutional containment and existing task approval controls remain enforced. Message authors cannot be supplied by clients.

## Verification in this workspace

- Next.js production build passed.
- SDK tests: 16 passed, including actual status interpretation and hierarchy mapping.
- Focused backend/architecture tests: 48 passed, 3 database tests skipped. Additional monorepo tests: 5 passed after correcting the new shared-model package boundary.
- Browser test with explicitly mocked API passed: map selection, task/project inspector, chat/replies, central composer, requirement-based staffing, changed-state popup and mobile width. This does not substitute for database integration tests.
- Architecture sections 1, 3, 5 and API compatibility checks passed.
- Full backend run: 563 passed, 202 skipped, two failures. One was the new package-boundary issue subsequently fixed and retested; the other was the pre-existing readiness test requiring an available PostgreSQL server. PostgreSQL could not be started under this execution environment's process-user restrictions.
- Real PostgreSQL tests are in tests/test_company_chat.py and run in the existing PostgreSQL CI jobs. The browser regression is also registered in CI.

## Explicit limits

This change does not make chat automatically execute arbitrary projects or produce AI replies. The UI explains that a connected runtime is required. It does not infer a hiring need from natural language, invent employees, grant CEO/CTO authority from a job title, or alter human review policy. The staffing form lets the owner record a requirement and create the needed profile. Project labels currently mean linked strategy plans, not a newly introduced project domain. A browser polling interruption can miss an ephemeral popup, but committed task transitions remain in the database timeline. Existing employee records do not prove a model is connected.

## Local update

Pull develop, run npm ci and npm run build from the repository root, then python scripts/package_frontend.py. In the backend terminal with AGO_POSTGRES_DSN configured, run python -m ago.event_runtime migrate and python -m ago.local_ops doctor. Restart the server on port 8010. Open /workspace/organization/.

Migration 048 is required before using the new conversation and staffing routes. No user database or local server was modified from this workspace.
