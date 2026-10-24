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
