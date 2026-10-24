# AGO local engineering-to-QA gate

Owner's operating policy: the laptop owner decides when processes run. No cloud, scheduled startup, background daemon, GitHub write, publication, or paid model is authorized by this procedure.

## What exists now

1. A previously approved agent run may contain a small Python engineering candidate. `apps/backend/ago/company_engineering.py` validates its exact JSON fields, paths, syntax, size, file digests, and non-release state. This does not prove the generated program works.
2. `scripts/ago_engineering_candidate.py` lets the human operator inspect and optionally stage exactly those files in a **new** local directory. The source cannot overwrite an existing destination. It may also stage an exact **unsubmitted** GitHub operation for the separately reviewed Section 34 delivery system.
3. `scripts/ago_verify_candidate.py` verifies manifest-to-files integrity again and, **only after explicit operator confirmation**, invokes the local Docker CLI. Docker has no network, cannot pull missing images, drops Linux capabilities, runs as non-root, and uses read-only files plus memory/CPU/process limits. It runs standard-library `unittest.TestCase` tests and refuses zero-test successes.
4. The test receipt records SHA-256 candidate identity, real test count and process status, and always says GitHub not committed, independent QA not approved, and release not ready. A true result is **local container unit-test evidence only**.

## Real owner-local Ollama smoke — proves only model connectivity

The P1 local-model acceptance gate needs an actual response from the *already-installed* model on the owner's laptop, not GitHub CI fake providers. The optional standalone proof does not start Ollama, touch GitHub or include a private project brief.

Preview without inference:

```powershell
$env:AGO_LLM_MODEL='qwen2.5-coder:1.5b'
python scripts/ago_local_model_smoke.py --output .\\ago-local-ollama-proof.json
```

After manually starting Ollama and enabling this shell session, run one bounded local inference:

```powershell
$env:AGO_LLM_PROVIDER='ollama_local'
$env:AGO_ENABLE_LOCAL_MODELS='true'
$env:AGO_LLM_MODEL='qwen2.5-coder:1.5b'
python scripts/ago_local_model_smoke.py --output .\\ago-local-ollama-proof.json --apply --confirm TEST_INSTALLED_LOCAL_MODEL
```

The newly created receipt records the model tag, an output digest, response byte count and elapsed time, but **not raw response content**. It is a self-reported local receipt; it does **not** establish GPU offloading, signed identity, real Founder project execution, independent QA, GitHub delivery or release. Do not share API tokens or confidential project content.

## Local failed-code repair — one deliberate proposal, never an automatic rerun

If the previous candidate's real offline Docker tests **failed**, the operator can request a single bounded local Ollama *source-only* repair. This uses a separately enabled already-installed **local model**, not a cloud endpoint, public repository or paid AI. It cannot modify original tests, documentation, acceptance checks, file names or QA verdicts.

Preview without calling a model:

```powershell
python scripts/ago_local_repair_proposal.py --staged-directory .\\reviewed-candidate --output .\\repair-proposal.json
```

After personally inspecting the original failing code and enabling only this shell session, explicitly allow a single local inference:

```powershell
$env:AGO_LLM_PROVIDER='ollama_local'
$env:AGO_ENABLE_LOCAL_MODELS='true'
$env:AGO_LOCAL_REPAIR_PROPOSALS='true'
$env:AGO_LLM_MODEL='qwen2.5-coder:1.5b'
python scripts/ago_local_repair_proposal.py --staged-directory .\\reviewed-candidate --output .\\repair-proposal.json --apply --confirm PROPOSE_ONE_LOCAL_SOURCE_REPAIR
```

The `repair-proposal.json` is a new **unapproved** candidate, not a proof of test pass. Review source changes and then stage/test that new candidate in a *new* folder:

```powershell
python scripts/ago_local_delivery_gate.py --input .\\repair-proposal.json --repair-from .\\reviewed-candidate --staged-directory .\\repaired-candidate --qa-output .\\repaired-qa-review.json
# After inspecting all source and unchanged original tests:
python scripts/ago_local_delivery_gate.py --input .\\repair-proposal.json --repair-from .\\reviewed-candidate --staged-directory .\\repaired-candidate --qa-output .\\repaired-qa-review.json --apply --confirm STAGE_TEST_AND_PREPARE_QA
```

The `--repair-from` directory is mandatory for repairs: its **original failed Docker receipt**, exact source digest, unchanged tests and unchanged acceptance checks are rechecked before any restaging or execution. A local repair proposal alone is *not* new Board approval. Direct candidate inputs are labeled separately in the preview.

A passing retest still needs a **separate authenticated human QA decision**. If it fails again, the same attempt cannot be reused; inspect evidence, start a new reviewed attempt or stop. No auto-replay after model or Docker timeouts.

Test stdout/stderr may contain confidential founder data. Current container receipts retain an SHA-256 digest, a **redacted** output marker and a fixed advisory failure category (such as assertion failure or missing module), never the raw private exception message. Only that bounded category can be included in the next local model's repair prompt. Existing historical receipts should still be handled as confidential.

## Exact P0 + P1 + P2 tracking

The reviewed, **incomplete** inventory is `docs/reports/AGO_P0_P1_P2_48_TASK_ACCEPTANCE.json`: 12 P0, 22 P1 and 14 P2 gates (48 total). Run `python scripts/check_ago_48_delivery_ledger.py` to fail closed if a gate is missing, reordered or falsely marked completed. A checklist or mocked CI is not a human QA verdict or market-ready product.

## Single-command manual delivery option

The separate inspection/staging/QA commands below remain supported. For a reviewed full-Board receipt, an optional **one-command local handoff** combines the same guarded steps. It neither runs automatically nor grants any GitHub permission.

Preview only:

```powershell
python scripts/ago_local_delivery_gate.py --input .\\review-receipt.json --staged-directory .\\reviewed-candidate --qa-output .\\ago-independent-qa-review.json
```

Only after personally reviewing the candidate's exact source and acceptance tests, and confirming that offline Docker is installed, explicitly allow local execution:

```powershell
python scripts/ago_local_delivery_gate.py --input .\\review-receipt.json --staged-directory .\\reviewed-candidate --qa-output .\\ago-independent-qa-review.json --apply --confirm STAGE_TEST_AND_PREPARE_QA
```

On failing tests, it retains the truthful failing receipt in the new staged directory and creates **no** QA packet. On passing tests, it creates only an **unsigned review request** outside the staged directory. Any optional GitHub draft needs four additional exact arguments (`--github-project-id`, `--github-operation-id`, `--github-expected-sha`, `--github-message`) and is never submitted by this command. Both output destinations must be new to prevent overwrites.

## Windows/PowerShell procedure

Prerequisite: AGO backend package installed in a supported virtual environment, Docker Desktop running by the owner's choice, and an existing local `python:3.11-slim` image. This procedure does not automatically install or download the image. If Docker cannot run safely, stop; do not use host Python on AI-generated source as a shortcut.

From the repository root, first preview the selected real agent receipt:

```powershell
python scripts/ago_engineering_candidate.py --input .\review-receipt.json --output .\reviewed-candidate
```

Inspect the candidate and its source. If its code, scope, and review status are acceptable, stage it intentionally:

```powershell
python scripts/ago_engineering_candidate.py --input .\review-receipt.json --output .\reviewed-candidate --apply --confirm WRITE_REVIEWED_CANDIDATE
```

Preview the exact staged QA scope and digest without running generated source:

```powershell
python scripts/ago_verify_candidate.py --staged-directory .\reviewed-candidate
```

Only after reading source/test files and confirming the local image exists, run:

```powershell
python scripts/ago_verify_candidate.py --staged-directory .\reviewed-candidate --apply --confirm EXECUTE_LOCAL_ISOLATED_TESTS
```

After a passing receipt, build a separate **independent QA review request**. Preview is read-only and does not require GitHub credentials:

```powershell
python scripts/ago_qa_review_packet.py --staged-directory .\\reviewed-candidate
```

Write one review packet **outside** the staged source directory only after deliberate confirmation:

```powershell
python scripts/ago_qa_review_packet.py --staged-directory .\\reviewed-candidate --output .\\ago-independent-qa-review.json --apply --confirm PREPARE_INDEPENDENT_QA_REVIEW
```

This packet binds the original candidate SHA-256, a digest of the local test receipt, exact file names, acceptance checks, and any still-unsubmitted GitHub draft ID. It **does not** identify an authenticated reviewer or grant approval. A local JSON receipt may be edited or forged by its owner, so AGO's separate signed-in human QA workflow must corroborate the actual source and test execution before GitHub dispatch or release. Do not manually change packet flags to pretend QA is done.

The resulting `AGO_TEST_RECEIPT.json` is written once under the staged directory. Do not reinterpret a CI-mocked test as a live local Docker execution. If the test fails, inspect the recorded output and stage a *new* reviewed candidate to retry. Do not overwrite a receipt or automatically rerun an uncertain outcome.

## Remaining local delivery gates after the Milestone A CI repair

- Current generator is intentionally bounded to small Python `src/` files and `tests/test_*.py` tests. The container runs **standard-library unittest**, not pytest plugins or arbitrary project build systems. A candidate with only pytest functions produces **zero unittest cases** and fails closed.
- GitHub Actions' **trusted synthetic fixture smoke** also runs a fixed correct and fixed deliberately broken Python source in a real non-root, read-only, no-network Docker container. It verifies that success and failure produce distinct truthful receipts. This is not execution of Ollama-generated code and does not prove real human QA.
- The Docker isolation flags reduce risk but do **not** guarantee containment of hostile source, prevent Docker engine vulnerabilities, or constitute an independent security assessment. If you do not trust the candidate, do not run it on the laptop.
- No actual local Docker execution on the owner's PC is established by repository tests; this is a tested, operator-triggered execution path requiring the user's machine and preloaded image.
- Independent QA must separately review program behavior, requirements coverage, evidence, security, and documentation. A generated unit test can miss bugs.
- `github_adapter.py` has an explicit opt-in, owner-scoped repository adapter; its operations require a signed approved action and the owner's locally configured `AGO_GITHUB_TOKEN`. This guide does not request, access, or store that secret.
- An unsubmitted GitHub operation draft is **not** an AGO-owned commit, PR, CI pass, or software release. Main remains owner-reviewed.
- Milestone A automated regression repair is verified at commit `36ca38f502c267f5442b6fa307eb6f096920f91e`: the nine-job architecture matrix is green, 912 backend tests pass with PostgreSQL, and 48 cross-device browser tests pass. Strategic Founder scope, bounded CEO reconciliation, and independent human operational/QA review have distinct gates; no test was skipped. This still does **not** prove a real local Ollama engineering run or finished product.
- A complete Founder→CEO→AI engineering→real test→independent QA→reviewed PR→CI→owner release demonstration remains required before calling AGO market-ready.

## Verified CI evidence and limitations

- Same-SHA full architecture, PostgreSQL foundation, and browser run: https://github.com/rudrasinha05/ago-/actions/runs/40011286092
- Same-SHA backend quality (912 passed, 1 warning): https://github.com/rudrasinha05/ago-/actions/runs/40011286117
- The six-device Playwright suite uses mocked API responses. It tests interface behavior and contract, not real GitHub commits made by AGO, genuine user-local model quality, or owner-installed software.
- Five project stage staffing assignments are persisted and tested on PostgreSQL; not all five stage deliverables execute automatically. Do not conflate staffing with AI completion.
- A real end-to-end demo still needs the **owner's own local** signed-in instance, actual Ollama output, deliberate Docker test, separate human QA verdict, reviewed AGO GitHub operation, draft PR, matching CI and owner release acceptance. Do not send GitHub tokens or model secrets in chat.

## Acceptance for this gate

Offline unit tests assert that review is read-only by default; exact confirmation is mandatory; staged digest and file contents cannot change; unknown files and links are rejected; optional unsubmitted GitHub draft files must match exact reviewed source; Docker command is network-disabled/read-only/unprivileged; zero-test and failing results never claim success; a passing mocked test never claims independent QA or release.


## Founder-started bounded live work and no-replay crash protection

The Company Map/Brain is a visual observer of the same persisted work records, not
a model kept artificially busy. Run the authenticated localhost AGO application
in one terminal. In a **separate** Windows PowerShell terminal, inspect the
approved-task preview and explicitly choose:

```powershell
.\scripts\ago.ps1 watch-approved-internal
```

The operator must sign in with a real founder account through hidden password prompting (no browser-token copy) and confirm. The worker
polls only already approved `internal:brief` tasks for **at most 60 minutes
or 10 attempted tasks**, sequentially, and can be stopped immediately with
Ctrl+C. It does not create projects, grant approvals, call GitHub, deploy code,
start itself on login, or execute any unapproved task. A separate human QA
verdict remains mandatory. Laptop powered off means no worker is running.

Applied dispatch writes one owner-local `~/.ago/approved_attempts` receipt
**before** the network request. Each filename is a SHA-256 of the task UUID,
not a token, private brief or model output. If a timeout or process crash makes
the server outcome uncertain, a later invocation skips the same task rather
than replaying its possible side effects. The operator must use AGO signed-in
task history and manual reconciliation; do not delete journal files merely to
force another attempt. A dry run never creates a journal entry. This is an
incremental P1 #128/#152/#154 safeguard, **not** evidence of live owner-device
operation, distributed scheduling, or a completed P2 release.


## Authenticated real AI run -> offline source review (no manual JSON copying)

When a real Founder-approved `internal:brief` model run has completed its
five independent **AI Board recommendations** plus Project Manager and
developer stages, AGO stores the resulting validated `engineering_candidate`
in `ago_agent_runs`. Previously the operator had to manually copy JSON
from a run and risk using the wrong task or a rejected Board candidate.

With the existing local server running, open a separate PowerShell terminal
in the repository root and run:

```powershell
.\scripts\ago.ps1 export-candidate
```

The operator enters the **exact completed run UUID** (from the Founder-visible
agent run record) and explicitly confirms; AGO writes the **new** JSON review file to the
private `~/.ago/candidate_exports/ago-run-<UUID>.json` folder, outside Git. AGO prompts for the actual Founder organization ID, email and hidden
password. Only localhost signed-in `GET /v1/console/me` and
`GET /v1/agents/runs` are read. A non-Founder, missing/failed run, uncleared
Board, missing unique AI staff, tampered code digest or existing output file
fails closed. No raw chat, token, founder brief or model prose is copied into
the export; only the exact validated code candidate and its original run IDs
are retained.

For example, after reviewing the private exported file
`~/.ago/candidate_exports/ago-run-<UUID>.json`, the **existing** delivery
gate can inspect it and, separately, stage and run offline Docker tests:

```powershell
python scripts/ago_local_delivery_gate.py --input "$HOME/.ago/candidate_exports/ago-run-<UUID>.json" --staged-directory "$HOME/.ago/candidate_stage_new" --qa-output "$HOME/.ago/qa-handoff-new.json"
# After independently reviewing the generated code, explicit confirmation only:
python scripts/ago_local_delivery_gate.py --input "$HOME/.ago/candidate_exports/ago-run-<UUID>.json" --staged-directory "$HOME/.ago/candidate_stage_new" --qa-output "$HOME/.ago/qa-handoff-new.json" --apply --confirm STAGE_TEST_AND_PREPARE_QA
```

The export itself never executes code, starts Ollama, calls GitHub, grants QA,
issues approvals, merges, publishes, or modifies the original run in PostgreSQL.
The Docker gate can create an **unprivileged pending human QA packet** only if
its isolated tests succeed. P2 completed-product acceptance still requires
human review and a genuine AGO-origin GitHub operation, and must not be
inferred from a local candidate or this export alone.


## Real local AI engineering startup — explicit Founder opt-in

The regular visual launcher does **not** enable models, so running the UI
alone never proves that AGO is coding. To launch the **same** local Company
Map and governed API with existing Ollama coding enabled for this foreground
process only, run:

```powershell
# Terminal 1: Ollama must already be installed and responsive (never auto pulled)
.\scripts\ago-visual.ps1 -Engineering -Model qwen2.5-coder:1.5b
# Terminal 2: After real Board appointments and Founder task approval in AGO
.\scripts\ago.ps1 run-approved-engineering
# Terminal 3: For a completed cleared AI run, export its candidate safely
.\scripts\ago.ps1 export-candidate
```

The opt-in launcher checks the exact installed model through the localhost
Ollama tags endpoint. It then enables `AGO_LLM_PROVIDER=ollama_local`,
`AGO_ENABLE_LOCAL_MODELS=true`, `AGO_LOCAL_COMPANY_CHAIN=true`,
`AGO_LOCAL_FULL_BOARD_REVIEW=true` and
`AGO_LOCAL_ENGINEERING_CANDIDATES=true` only while that foreground AGO
server runs; previous process-level model settings are restored when the
launcher exits. The local endpoint is not auto-started; the model is never
downloaded and no cloud/paid fallback is permitted. A missing real appointed
five-seat Board, distinct PM and worker, inactive project, denied Board
recommendation or missing task approval blocks code generation.

This mode enables **actual** model attempts, not guaranteed passing source.
A successful AI reply is still untrusted code; the independent offline Docker
review, QA and approved GitHub delivery remain separate gates.


### Preventing accidental deterministic-stub completion

`run-approved-engineering` is separate from the generic
`run-approved-internal` command. Before any execution POST, it requires an
authenticated Founder-visible read of
`GET /v1/agents/engineering-capabilities`, which must confirm all six
current-server opt-in settings: development mode, local Ollama provider,
enabled local models, full company chain, complete five-seat Board review,
and engineering-candidate generation. If the server was started normally
without `-Engineering`, the command **refuses the task without consuming
approval or starting deterministic fallback work**.

The capabilities endpoint is a configured-mode preflight only. It expressly
reports `model_inference_verified=false` and does not assert that Ollama is
live, the Board is staffed, the task is approved, tests passed, GitHub is
connected, or any product is releasable. The server remains the final
authorization authority on a subsequent dispatch.


### Faster source-reviewed Docker → QA handoff (one Windows operator action)

After the authenticated `export-candidate` step, the Founder can now run:

```powershell
.\scripts\ago.ps1 test-exported-candidate
```

Enter the existing run UUID. AGO locates the private code under
`~/.ago/candidate_exports/`, previews the recorded five-seat Board source
and prints the exact candidate SHA-256 and file list. Inspect the original
exported JSON's actual code and tests, then explicitly authorize Docker
with `TEST_REVIEWED_AI_CANDIDATE`.

The command creates a fresh, unique private stage and a QA packet under
`~/.ago/delivery_runs/` and passes the **same reviewed candidate SHA** into
the offline Docker executor. A changed candidate between preview and apply
is rejected *before staging or execution*. Failed isolated tests never
produce a positive independent-QA verdict or a GitHub operation.
A passing container test produces only a pending human QA review packet,
not an approval, PR or release. The existing lower-level scripts remain
available for advanced and failure-reconciliation use.


### Real local P2 repair loop (explicit, original tests immutable)

For a **failed** `ago.ps1 test-exported-candidate` run, copy the
`stage-...` location printed **before** the Docker invocation. The
PowerShell operator supports a deliberately separate review and repair flow:

```powershell
.\scripts\ago-repair.ps1 -Mode preview -FailedStage "$HOME\.ago\delivery_runs\stage-..."
.\scripts\ago-repair.ps1 -Mode propose -FailedStage "$HOME\.ago\delivery_runs\stage-..."
.\scripts\ago-repair.ps1 -Mode retest -FailedStage "$HOME\.ago\delivery_runs\stage-..." -Proposal "$HOME\.ago\delivery_runs\repair-....json"
```

Preview validates the exact failed source and Docker receipt without
inference. Propose verifies an already installed localhost Ollama model,
asks explicit confirmation, performs **one** source-only proposal and
restores the original model flags. It never changes test files, the
acceptance plan, or previous failed evidence. No automatic attempt
retries are launched.

Retest requires the **separate** original staged failure and the saved
unapproved proposal. AGO checks the same source/test paths and exact
preserved acceptance checks, prints the new SHA, asks a second separate
authorization, pins that digest and uses a fresh offline Docker stage.
Only a passing retest produces a still-unapproved independent human QA
packet. No source is silently published or committed to GitHub.


### Authenticated independent human QA bridge

After a **real** passing Docker run has created its pending `qa-....json`,
the reviewer can run `scripts/ago_human_qa_handoff.py` in **preview** mode
with the exact private exported Board-cleared source file, the matching
staged Docker directory, pending QA packet, chosen human verdict and
substantive review notes. The script logs in to AGO using the **separate
human QA reviewer's own credentials**, checks `qa:review` and `qa:read`,
matches the completed unreviewed task ID against the authenticated
`/v1/console/qa-queue`, verifies that the worker is not the reviewer,
and reconstructs the candidate SHA and passing test-receipt hash.

After independently examining the generated code, acceptance requirements
and failing cases, the human can explicitly pass `--apply --confirm
INDEPENDENT_HUMAN_QA_DECISION`. A durable local no-replay marker is written
**before** the actual `POST /v1/tasks/<UUID>/review`. If the network result
is uncertain, the operator must inspect AGO review state rather than retry.
The server itself enforces an actual human reviewer separate from the
AI assignee and persists the QA verdict. A positive result is reported only
when AGO confirms the exact verdict, reviewer and evidence.

No GitHub connector or release is invoked by this review helper.


To submit an independently completed **human** review through the
actual AGO API, run:

```powershell
.\scripts\ago.ps1 review-tested-candidate
```

Enter the original completed run UUID, the exact passing Docker stage,
the pending QA packet JSON path, `pass` or `fail`, substantive
review notes, and the explicit confirmation. Authenticate as an active
human reviewer granted `qa:review` and `qa:read`, **not the AI worker**.
Only an unreviewed, completed task in that tenant's QA queue can receive
a verdict. The server records the review durably; client-side evidence
remains untrusted and cannot impersonate an independent reviewer.
The request has a durable pre-POST no-replay marker. If review submission
times out, inspect AGO QA queue/review state before taking any new action.
No GitHub write or release follows automatically.


### Authenticated QA-passed source → unexecuted GitHub draft

A Founder can prepare a **local, reviewable** Section34 `commit_files`
operation only after AGO's actual persisted human QA record contains
`pass` for the same completed task, with exact origin run UUID, project,
candidate SHA-256 and Docker receipt SHA-256.

Run `python scripts/ago_prepare_github_handoff.py --help` for the
read-only preview and separately confirmed export command. Supply the
original Board-cleared exported JSON, passed Docker stage, exact pending QA
packet, and explicit AGO GitHub project ID, new operation UUID, reviewed
`develop` SHA and human-readable commit message. The helper prompts for
the active Founder account and verifies `GET /v1/tasks/<task>/review`
against those local bytes.

A negative or missing human verdict, changed candidate, altered tests,
different task/receipt, or unknown reviewer stops operation creation.
The draft remains **private, unsubmitted, and unapproved**. Its remote
HEAD is deliberately not certified by this helper; AGO's existing
reviewed GitHub operation service and non-force develop compare-and-swap
must independently authorize any actual network write. No PR, release
or merge is created here.


The convenient Windows operator flow for this same reviewed draft is:

```powershell
.\scripts\ago.ps1 prepare-github-draft
```

Provide the original completed run ID, passing Docker stage and QA packet;
the **AGO GitHub integration project UUID** (not the founder intake ID);
the currently reviewed develop HEAD SHA, and a commit message.
Authenticate as the real Founder and approve the separate draft action.
AGO creates a **new private JSON draft** under `~/.ago/delivery_runs/`.
Nothing is sent to GitHub, and no external head/CI/release evidence is
assumed. The existing governed GitHub service must separately review,
authorize, compare the remote develop SHA and execute any eventual commit.


### Submit a human-QA-verified GitHub draft into AGO governance

`python scripts/ago_submit_github_proposal.py --help` supports a
read-only preview and a distinct, explicit confirmed proposal. Supply the
exact private QA-verified draft, original Board-cleared export, passed
Docker source staging directory and local pending QA packet. The operator
logs in as the Founder; AGO re-reads the persisted human `pass` review
and currently committed source bytes, revalidates the entire `commit_files`
payload, fetches the **live integration domain revision**, and creates
one immutable, *pending* `github_operation` through
`POST /v1/enterprise/reviews/integration/propose` only after an explicit
`SUBMIT_QA_VERIFIED_GITHUB_PROPOSAL` confirmation.

The helper writes a no-replay receipt before the POST. A timeout means
**uncertain**; inspect the AGO governance proposal and approval inbox rather
than retrying a new operation. This step does not apply the proposal,
approve it, call the GitHub provider, merge a PR, or mark a release ready.
An independently authorized enterprise review and later Founder-triggered
GitHub execution are still mandatory.


For the Founder Windows interface, invoke:

```powershell
.\scripts\ago.ps1 submit-github-proposal
```

Enter the exact completed run and saved draft operation UUIDs, original
passing Docker stage and QA packet. Authenticate as the real Founder and
confirm. The result is an **AGO enterprise review proposal** awaiting
independent approval—not a GitHub commit. Review the proposal in AGO's
enterprise integration governance and perform the separate approved
apply/execute operations when permitted.
