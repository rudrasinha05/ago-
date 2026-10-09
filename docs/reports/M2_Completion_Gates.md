# M2 implementation and acceptance gates

## Implemented foundations on develop
- Corporate constitution conservative classification
- Approval request/decision model and transactional persistence
- Tenant RBAC check integration
- Department and employee models with PostgreSQL adapters
- Governed task state machine and PostgreSQL task transitions
- Independent QA domain review
- Tenant-scoped memory model and PostgreSQL adapter
- Migrations 004 and 005
- Automated unit-level security and contract tests

## Open acceptance gates — DO NOT mark M2 complete
- Run migrations 004 and 005 against PostgreSQL and test all foreign keys.
- Run full lint/test suite; new tests have not been executed in the user's environment.
- Add end-to-end PostgreSQL integration tests for organization, memory, approval, and tasks.
- Enforce authorization on every exposed API and tool adapter, and record tamper-resistant audit.
- Implement durable review/QA records and actual execution adapters.
- Validate reviewer identity and role permissions against trusted authentication; avoid untrusted authorized flags.
- Check tenant-scoped approval/task references, concurrency and rollback behavior.
- Record HTTP readiness result for M1 if still missing.

Founder requested continued development without pull commands until they ask. No local actions are requested here.
