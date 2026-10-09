# M1 PostgreSQL verification (Windows PowerShell)

Use an isolated disposable database, never production. PostgreSQL 15+ recommended.

1. Install PostgreSQL if not installed and ensure `psql` works.
2. From an administrator account create a dedicated database and user:
   ```sql
   CREATE USER ago_test WITH PASSWORD 'REPLACE_WITH_STRONG_TEST_PASSWORD';
   CREATE DATABASE ago_test OWNER ago_test;
   ```
   Run CREATE DATABASE outside any explicit transaction.
3. In `apps/backend` PowerShell set:
   ```powershell
   $env:AGO_POSTGRES_DSN = "postgresql://ago_test:REPLACE_WITH_STRONG_TEST_PASSWORD@localhost:5432/ago_test"
   $env:AGO_TEST_POSTGRES_DSN = $env:AGO_POSTGRES_DSN
   python -m ago.event_runtime migrate
   python -m pytest -q --basetemp="C:\ago-pytest-temp"
   python -m uvicorn ago.main:app --reload
   ```
4. `/health/ready` returns HTTP 200 only if PostgreSQL SELECT 1 succeeds. Missing/failed database returns HTTP 503; `/health/live` remains 200.

Security: environment variables are local to this PowerShell session; do not commit credentials. A passing PostgreSQL check is a foundation gate, not proof of production security or complete infrastructure readiness.
