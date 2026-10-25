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

This command prompts privately for founder login, previews eligible tasks
without changes, then separately requires an explicit typed confirmation.
Its success must contain a `verified_seven_role_handoffs` receipt with seven
distinct employee UUIDs, five advisory Board APPROVE lines and actual bounded
per-role inference durations, linked by one real AGO run ID. Private draft
text, founder briefs and generated source are not printed in that receipt.

An unverified Board vote, veto, model JSON/schema failure or incomplete
employee staffing is a genuine blocking result, not seven-role success.
After ambiguous network outcome, do not retry the same task; the local
`~/.ago/approved_attempts` journal blocks accidental replay. Reconcile
with the authenticated backend run before requesting a new approved task.

This only proves seven-role *sequential drafting*, not seven independently
authorized executable subtasks, human QA, runnable product or GitHub release.
The founder starts/stops local components; no auto-download, cloud fallback
or unattended process is configured.
