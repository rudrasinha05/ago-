# AGO local engineering-to-QA gate

Owner's operating policy: the laptop owner decides when processes run. No cloud, scheduled startup, background daemon, GitHub write, publication, or paid model is authorized by this procedure.

## What exists now

1. A previously approved agent run may contain a small Python engineering candidate. `apps/backend/ago/company_engineering.py` validates its exact JSON fields, paths, syntax, size, file digests, and non-release state. This does not prove the generated program works.
2. `scripts/ago_engineering_candidate.py` lets the human operator inspect and optionally stage exactly those files in a **new** local directory. The source cannot overwrite an existing destination. It may also stage an exact **unsubmitted** GitHub operation for the separately reviewed Section 34 delivery system.
3. `scripts/ago_verify_candidate.py` verifies manifest-to-files integrity again and, **only after explicit operator confirmation**, invokes the local Docker CLI. Docker has no network, cannot pull missing images, drops Linux capabilities, runs as non-root, and uses read-only files plus memory/CPU/process limits. It runs standard-library `unittest.TestCase` tests and refuses zero-test successes.
4. The test receipt records SHA-256 candidate identity, real test count and process status, and always says GitHub not committed, independent QA not approved, and release not ready. A true result is **local container unit-test evidence only**.

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

The resulting `AGO_TEST_RECEIPT.json` is written once under the staged directory. Do not reinterpret a CI-mocked test as a live local Docker execution. If the test fails, inspect the recorded output and stage a *new* reviewed candidate to retry. Do not overwrite a receipt or automatically rerun an uncertain outcome.

## Remaining local delivery gates after the Milestone A CI repair

- Current generator is intentionally bounded to small Python `src/` files and `tests/test_*.py` tests. The container runs **standard-library unittest**, not pytest plugins or arbitrary project build systems. A candidate with only pytest functions produces **zero unittest cases** and fails closed.
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
