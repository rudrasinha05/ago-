# AGO P1: real seven-role founder-laptop test

The owner has already confirmed one `qwen2.5-coder:1.5b` Ollama inference
on `127.0.0.1:11434`, and `ollama ps` reported `100% GPU` model loading.
This is NOT proof that the seven AGO employees executed a governed task.

## Terminal A: start AGO with explicit local seven-role flags

```powershell
cd C:\Users\rudra\Projects\ago-
git pull --ff-only origin develop
$env:AGO_ENVIRONMENT = "development"
$env:AGO_LLM_PROVIDER = "ollama_local"
$env:AGO_ENABLE_LOCAL_MODELS = "true"
$env:AGO_ENABLE_PAID_MODELS = "false"
$env:AGO_LOCAL_COMPANY_CHAIN = "true"
$env:AGO_LOCAL_FULL_BOARD_REVIEW = "true"
$env:AGO_LOCAL_ENGINEERING_CANDIDATES = "true"
$env:AGO_LLM_MODEL = "qwen2.5-coder:1.5b"
.\scripts\ago.ps1 serve
```

Keep the existing local PostgreSQL configuration. The founder must first
have an ACTIVE approved company project, five distinct founder-appointed AI
Board directors (CEO/CTO/Finance/Risk/Quality), an actual AI PM and separate
AI employee reporting to that PM, and a genuinely approved linked discovery
`internal:brief` task. This script creates none of those automatically.

## Terminal B: preview and founder-confirmed dispatch

```powershell
cd C:\Users\rudra\Projects\ago-
.\scripts\ago.ps1 run-approved-engineering
```

This command prompts privately for founder login **once**, previews at most
one eligible task without any write, then asks for the exact typed confirmation
in the same authenticated process. If zero eligible tasks exist, it stops
without attempting an AI inference or creating a journal record. Cancellation
also performs no task POST. Each confirmed run retains a durable no-replay
attempt claim before network I/O.
Its success must contain a `verified_seven_role_handoffs` receipt with seven
distinct employee UUIDs, five advisory Board APPROVE lines and actual bounded
per-role inference durations, linked by one real AGO run ID. Private draft
text, founder briefs and generated source are not printed in that receipt.

If an older attempt ends in `HTTPError`, do NOT launch engineering again to
repeat it. Instead keep AGO server running and invoke:

```powershell
.\\scripts\\ago.ps1 reconcile-approved-engineering
```

Sign in once. The read-only command matches the saved hashed attempt receipts
in `~/.ago/approved_attempts` against the newest 100 founder-visible agent
runs and company task rows. It prints safe statuses, failure codes, and run IDs,
never model drafts or founder briefs. A missing run in these bounded results
**cannot prove the task was never started**. The next confirmed attempt needs
a separately approved new task; do not delete attempt records to force replay.
The upgraded execution CLI also prints an HTTP status (e.g., 403 preflight or
502 agent handler failure), without exposing potentially sensitive server bodies.

An unverified Board vote, veto, model JSON/schema failure or incomplete
employee staffing is a genuine blocking result, not seven-role success.
After ambiguous network outcome, do not retry the same task; the local
`~/.ago/approved_attempts` journal blocks accidental replay. Reconcile
with the authenticated backend run before requesting a new approved task.

This only proves seven-role *sequential drafting*, not seven independently
authorized executable subtasks, human QA, runnable product or GitHub release.
The founder starts/stops local components; no auto-download, cloud fallback
or unattended process is configured.
