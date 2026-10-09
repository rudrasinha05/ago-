# M2 PostgreSQL integration acceptance tests

Added `tests/test_m2_postgres_integration.py` for:
- Department and employee persistence
- Tenant-scoped employee listings
- Private organizational memory reads and cross-tenant isolation
- Approval request/decision audit lifecycle
- Governed task state transitions with live RBAC lookup
- Denial before approval and prevention of repeated task starts

Tests require a migrated disposable PostgreSQL database and `AGO_TEST_POSTGRES_DSN`.
They are **not yet executed** in the founder's environment.

Important: current DB connection tests use transactional fixtures; verify cleanup behavior under psycopg nested transactions before accepting as green. Never point these tests at production.

Remaining M2 blockers include durable QA, trusted authenticated API wiring, execution adapter authorization, and audit tamper protection. Do not mark M2 complete without these.
