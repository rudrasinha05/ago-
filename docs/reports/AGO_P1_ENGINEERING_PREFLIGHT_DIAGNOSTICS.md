# AGO P1: read-only diagnosis after a first real-engineering HTTPError

The task remains `waiting_approval` and there are zero persisted
`ago_agent_runs` in the first observed laptop reconciliation. This narrows
down the execution failure to **pre-run authorization/preflight**, not a
verified completed seven-employee inference. An authorized task can still
remain in `waiting_approval` before dispatch; this status alone does not
establish missing approval.

## After pulling latest develop

A server restart is required to activate the new GET endpoint. Stop the
**existing** foreground AGO server with Ctrl+C; do not change local DB,
credentials, plans, tasks, tenants, approvals or migration state. Start the
same existing AGO server again with the previous explicit local model flags
and original local DB environment, then run:

```powershell
.\scripts\ago.ps1 diagnose-approved-engineering
```

Enter the previously attempted exact task ID when prompted. Authenticated
founder login is required. The service uses SQL `SET TRANSACTION READ ONLY`
on the localhost PostgreSQL connection and never calls the task runner,
calendar denial writer, Ollama, credit charge, governance decision or GitHub.
It does not create/change a no-replay attempt receipt.

The result reports task state, true *linked* approval status, existence of
the original founder's approved discovery scope, real five-seat AI Board
appointments and seven distinct staffed PM/worker identities, plus the
recorded outcome of any actual run.

Even when `checked_preconditions_pass=true`, calendar, constitutional
and behavior execution gates, virtual credit budget and model output remain
unverified. The response always has `task_post_authorized=false`.

**Never replay the original hashed journal attempt.** This diagnostic
identifies the applicable next governance/staffing step; a fresh execution
requires a separate new approved task. Any missing app permission or human
decision remains a real block, not something to bypass with new fake staff
or modified SQL.
