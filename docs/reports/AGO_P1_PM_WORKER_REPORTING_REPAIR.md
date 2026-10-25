# AGO P1 PM → Worker reporting link repair

Previous founder-local evidence: five real software AI officers have been
appointed. The ORIGINAL approved discovery task is still read-only diagnosed
as \`worker_pm_reporting_path_missing\`. This is a real missing path in the
existing recorded company hierarchy, NOT a request to create a replacement PM.

The founder-scoped original \`GET /v1/agents/tasks/{task_id}/engineering-preflight\`
now shows \`reporting_repair_evidence\` ONLY for this blocker, with the existing
worker UUID, accountable PM UUID, current manager UUID and names. Identity
is checked against actual tenant-owned ACTIVE founder discovery step. It is
read-only and never reports task prompt, project brief or model generated code.

## Founder Windows commands

Update GitHub and RESTART local AGO server after pulling Python backend changes,
keeping the same existing database, tenant and local-only Ollama configuration.

From a SECOND PowerShell after the server is running, READ-ONLY preview:

\`\`\`powershell
python .\\scripts\\ago_pm_reporting_repair.py --task-id f0f990f6-d823-43a2-8e66-54bd3f5f23cb
\`\`\`

This prints recorded worker, PM and current manager. The script defaults
to no writes. If current manager is NULL and the preview says
\`link_worker_to_existing_pm\`, apply the **one** required manager link after
the Founder types \`LINK_AGO_WORKER_TO_ACCOUNTABLE_PM\`:

\`\`\`powershell
python .\\scripts\\ago_pm_reporting_repair.py --task-id f0f990f6-d823-43a2-8e66-54bd3f5f23cb --apply
\`\`\`

If the worker ALREADY reports to another manager, preview prints
\`requires_explicit_reparent_opt_in\` and makes NO change. The founder must
inspect the worker's existing duties: change that relationship only with:

\`\`\`powershell
python .\\scripts\\ago_pm_reporting_repair.py --task-id f0f990f6-d823-43a2-8e66-54bd3f5f23cb --reparent
\`\`\`

Only if that change is appropriate, add \`--apply\`. Never blindly overwrite
real reporting structure to achieve a green status.

The write operation is the existing governed Founder-only
\`PUT /v1/organization/company/employees/{worker_id}/manager\`
and the backend independently rejects cross-tenant identities and cycles.
Script rechecks live task and company state before one PUT, and fetches
read-only preflight after it. It never invokes the original task run,
approves work, adds employees, fabricates QA or writes GitHub.

The previous confirmed engineering attempt already has a no-replay receipt.
**Do not run that original task.** Even with seven-role hierarchy verified,
a new separately approved linked task is required for the future live run.
