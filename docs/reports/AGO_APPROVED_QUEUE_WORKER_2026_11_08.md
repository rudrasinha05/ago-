# AGO approved offline queue worker — Founder local acceptance

Only previously approved internal:brief tasks. Explicit bounded process; never auto-starts at boot or through the web app. The real AGO server checks founder identity, signed approvals, tenant, worker, calendar, QA dependencies, capacity, and live task permissions. No auto hiring, independent QA approval, paid AI execution, GitHub write or release.

Read-only preview from repository root on Windows:

    py scripts/ago_approved_queue_worker.py --local-url http://127.0.0.1:8010 --login

Founder authorizes one bounded session (two tasks, five minutes):

    py scripts/ago_approved_queue_worker.py --local-url http://127.0.0.1:8010 --login --apply --confirm EXECUTE_APPROVED_INTERNAL_TASKS --minutes 5 --max-tasks 2

Stop with Ctrl+C. A private local journal at ~/.ago/approved_attempts fsyncs before each task POST. Any error, unknown remote outcome, expired lease or permission denial stops that task; it is NEVER automatically replayed. Reconcile separately with exact signed task/run evidence. Owner database not altered by documentation/CI; integration tests use disposable migrated PostgreSQL.

Frozen checklist: PROJ-006, ACC-152 remain Partial: no always-on unattended project build or release. Do not claim software delivery because an internal brief packet was generated.
