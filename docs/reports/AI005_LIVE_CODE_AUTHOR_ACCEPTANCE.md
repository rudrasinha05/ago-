# AI-005 live code-author acceptance — owner-local proof, not a completed AGO release

This procedure uses the existing free local Ollama installation. It never
downloads a model, purchases infrastructure, starts a server, commits GitHub
source, bypasses Founder authority, or authorizes independent QA.

## A. Safe standalone model capability check

From a repository checkout containing the AI-005 fixes, activate the **existing**
backend Python environment. The local Ollama service and the already installed
`qwen2.5-coder:3b` model must be started by the laptop owner, not by AGO.

The Python script has a read-only preview mode:

```powershell
$env:AGO_ENVIRONMENT = 'development'
$env:AGO_LLM_PROVIDER = 'ollama_local'
$env:AGO_ENABLE_LOCAL_MODELS = 'true'
$env:AGO_ENABLE_PAID_MODELS = 'false'
$env:AGO_LLM_MODEL = 'qwen2.5-coder:3b'
python scripts/ago_local_engineering_probe.py --output "$HOME\ago-ai005-code-probe.json"
```

After reviewing the bounded local-only behavior, an explicit one-call inference:

```powershell
python scripts/ago_local_engineering_probe.py --output "$HOME\ago-ai005-code-probe.json" --apply --confirm PROBE_INSTALLED_ENGINEERING_MODEL
```

Expected receipt: `code_candidate_static_reviewed=true`, one or more source
and test files, a 64-character `candidate_sha256`, and
`local_ollama_response_observed=true` only when the real localhost provider
responded. If the model creates invalid JSON, unsafe paths, malformed Python or
undiscoverable unittest tests, the probe fails closed and does not create the
receipt. Retry only by a fresh deliberate invocation after inspecting the failure.
Do not copy a raw private model response into GitHub issues or CI.

**Evidence boundary:** This one-call probe does not run code or prove an AGO
employee generated code under a real Founder task. The receipt always says
`real_ago_founder_task_executed=false`, `board_approval_verified=false`,
`tests_executed=false`, `github_committed=false` and `release_ready=false`.
The generated source itself is never saved by this probe.

## B. Full real AGO seven-role and implementation-stage acceptance

To satisfy checklist **AI-005**, keep the existing Founder project, staffing,
approvals and model opt-in. Run the real AGO task via the authorized signed
Founder UI/API, not a simulated CI fixture. Confirm all five real Board seats,
real CEO/CTO/PM/developer reporting, approved project scope, specifically
activated **implementation** stage, linked task approval, available virtual
credits, and a reachable installed local model. A diagnosis without mutation:

```powershell
.\scripts\ago.ps1 diagnose-approved-engineering
```

Do not replay a failed/unknown attempt or reuse an old operation key to suppress
safety checks. Only a **new authorized task** can be dispatched. The expected
server record has seven distinct ordered role handoffs, five verifiable Board
recommendations and an `engineering_candidate_status=syntax_reviewed` with an
unchanged source/test candidate digest. A direct model probe cannot substitute
for this signed, persisted AGO result.

## C. Exact candidate → Docker → pending independent QA

After a genuine completed authorized run, the Founder can export just that
run's source/test candidate, outside the repo, using the exact UUID displayed by
AGO:

```powershell
python scripts/ago_pull_candidate.py --run-id YOUR_COMPLETED_RUN_UUID --output "$HOME\ago-engineering-run.json" --apply --confirm EXPORT_APPROVED_AI_CANDIDATE
```

Review the generated source and tests manually. With an existing locally
available `python:3.11-slim` Docker image and explicitly running Docker Desktop,
use the guarded single handoff (replace paths with new, unused paths):

```powershell
python scripts/ago_local_delivery_gate.py --input "$HOME\ago-engineering-run.json" --staged-directory "$HOME\ago-ai005-reviewed" --qa-output "$HOME\ago-ai005-qa-pending.json"
python scripts/ago_local_delivery_gate.py --input "$HOME\ago-engineering-run.json" --staged-directory "$HOME\ago-ai005-reviewed" --qa-output "$HOME\ago-ai005-qa-pending.json" --apply --confirm STAGE_TEST_AND_PREPARE_QA
```

A failed Docker run retains a failed receipt and cannot produce a passing QA
packet. A passing run only prepares a **pending independent human QA** review;
the human QA decision, AGO-owned GitHub credential, separately reviewed
commit/PR, release and Founder acceptance remain separate outstanding gates.

## D. Acceptance boundaries and checklist status

- CI with synthetic Board/model responses + actual Docker trusted fixtures proves
  implementation regressions, not owner's Ollama or a released project.
- A successful standalone local model probe proves only model code-author
  capability and static checks.
- **AI-005 becomes DONE only** with a persisted authorized AGO employee run
  containing valid source and tests at the implementation stage, plus the
  agreed independent evidence. QA-002/003 additionally require execution of
  that exact candidate on the owner's Docker; GitHub delivery is distinct.
- No status or source file should be marked released until all real gates pass.
