<#
.SYNOPSIS
AGO local Windows operator console (never fetches Git or touches production).
.EXAMPLE
.\scripts\ago.ps1 doctor
.\scripts\ago.ps1 init
.\scripts\ago.ps1 serve
.\scripts\ago.ps1 migrate
.\scripts\ago.ps1 market-watch  # opt-in in a separate terminal, Ctrl+C stops
.\scripts\ago.ps1 safe-reconcile  # manual stale-run recovery, no replay
.\scripts\ago.ps1 run-approved-internal  # only previously approved local internal AI briefs
.\scripts\ago.ps1 run-approved-engineering  # refuse non-Ollama fallback; real 7-role AI coding
.\scripts\ago.ps1 reconcile-approved-engineering  # read-only inspection of failed/no-replay attempts
.\scripts\ago.ps1 diagnose-approved-engineering  # read-only task-specific Board/PM approval checks
.\scripts\ago.ps1 watch-approved-internal  # up to 60 minutes or 10 tasks; Ctrl+C stops
.\scripts\ago.ps1 export-candidate  # exact completed Board-cleared AI run -> new local source review
.\scripts\ago.ps1 test-exported-candidate  # reviewed source -> Docker -> pending independent QA
.\scripts\ago.ps1 review-tested-candidate  # authenticated independent human QA decision
.\scripts\ago.ps1 prepare-github-draft  # human-QA-passed code -> private, unsubmitted GitHub draft
.\scripts\ago.ps1 submit-github-proposal  # explicit Founder governance proposal, NOT a GitHub push
.\scripts\ago.ps1 apply-github-proposal  # after independent human approval; AGO only
.\scripts\ago.ps1 execute-github-commit  # after approved apply; explicit real GitHub commit
#>
param(
    [ValidateSet("doctor", "tenants", "init", "init-solo", "serve", "migrate", "test", "market-watch", "company-pulse", "safe-reconcile", "run-approved-internal", "run-approved-engineering", "reconcile-approved-engineering", "diagnose-approved-engineering", "watch-approved-internal", "export-candidate", "test-exported-candidate", "review-tested-candidate", "prepare-github-draft", "submit-github-proposal", "apply-github-proposal", "execute-github-commit")]
    [string]$Action = "doctor",
    [ValidateRange(1024,65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $RepoRoot "apps\backend"
# Resolve legacy exports AND reviewed one-attempt live-to-QA bridge receipts.
# Never guess the newest candidate or select a different run by filename.
function Resolve-AGOExportReceipt {
    param([string]$RunId)
    $Base = Join-Path $HOME ".ago\candidate_exports"
    $Legacy = Join-Path $Base ("ago-run-" + $RunId + ".json")
    if (Test-Path -LiteralPath $Legacy -PathType Leaf) {
        $Chosen = $Legacy
    } else {
        $Chosen = Read-Host "Exact private export JSON from the live-to-QA bridge"
    }
    if (-not (Test-Path -LiteralPath $Base -PathType Container) -or
        -not (Test-Path -LiteralPath $Chosen -PathType Leaf)) {
        throw "Original private exported AI source receipt is required."
    }
    $Full = (Resolve-Path -LiteralPath $Chosen).Path
    $Root = (Resolve-Path -LiteralPath $Base).Path
    if (-not $Full.StartsWith(
        $Root.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar,
        [StringComparison]::OrdinalIgnoreCase)) {
        throw "AI source receipt must remain under the private AGO candidate_exports directory."
    }
    $Receipt = Get-Content -LiteralPath $Full -Raw | ConvertFrom-Json
    if ($Receipt.id -cne $RunId -or
        $Receipt.source -cne "ago_authenticated_founder_run" -or
        $Receipt.status -cne "completed" -or
        $Receipt.result.board_review_cleared -ne $true) {
        throw "Private export does not match the exact completed Board-cleared AGO run."
    }
    return $Full
}
if (-not (Test-Path (Join-Path $BackendPath "ago\local_ops.py"))) {
    throw "AGO backend is missing. Run from the synced AGO repository."
}
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    throw "Python 3.11+ is required. Install Python before running AGO."
}
$CurrentStage = $env:AGO_ENVIRONMENT
if ($CurrentStage -and $CurrentStage.ToLowerInvariant() -notin @(
    "development", "test", "testing"
)) {
    throw "This script is local-only. Production and staging are not supported."
}
Push-Location $BackendPath
try {
    if ($Action -eq "migrate") {
        if (-not $env:AGO_POSTGRES_DSN) {
            throw "AGO_POSTGRES_DSN is missing; migration cancelled."
        }
        & python -c "import os,sys; from ago.local_ops import local_database; sys.exit(0 if local_database(os.getenv('AGO_POSTGRES_DSN', '')) else 3)"
        if ($LASTEXITCODE -ne 0) {
            throw "Migration refused: only a localhost PostgreSQL database is supported by this helper."
        }
        # No automatic migration. Never run this against production or shared test data.
        $Confirmation = Read-Host "This applies SQL migrations to your configured database. Type MIGRATE"
        if ($Confirmation -cne "MIGRATE") {
            Write-Host "Migration cancelled. No changes requested."
            exit 2
        }
        & python -m ago.event_runtime migrate
        exit $LASTEXITCODE
    }
    if ($Action -eq "test") {
        if (-not $env:AGO_TEST_POSTGRES_DSN) {
            throw "A separate disposable AGO_TEST_POSTGRES_DSN is required."
        }
        if ($env:AGO_TEST_POSTGRES_DSN -eq $env:AGO_POSTGRES_DSN) {
            throw "Test and application PostgreSQL DSNs must be different."
        }
        & python -m ruff check ago tests tests_browser
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        & python -m pytest -q --basetemp="C:\ago-pytest-temp"
        exit $LASTEXITCODE
    }
    if ($Action -eq "company-pulse") {
        if (-not $env:AGO_MARKET_TENANT_ID) {
            throw "Specify the existing AGO_MARKET_TENANT_ID for a tenant-scoped read-only pulse."
        }
        & python ../../scripts/company_readiness_audit.py --tenant-id $env:AGO_MARKET_TENANT_ID
        exit $LASTEXITCODE
    }
    if ($Action -eq "diagnose-approved-engineering") {
        $TaskId = Read-Host "Previously attempted AGO internal:brief task UUID (read-only)"
        if ($TaskId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "A valid task UUID is required for read-only inspection."
        }
        Write-Host "Checking stored approval, active project and seven actual employee identities only."
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login --diagnose-task $TaskId
        exit $LASTEXITCODE
    }
    if ($Action -eq "reconcile-approved-engineering") {
        Write-Host "Read-only reconciliation; never replay a previous HTTPError task."
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login --reconcile-only
        exit $LASTEXITCODE
    }
    if ($Action -in @("run-approved-internal", "run-approved-engineering", "watch-approved-internal")) {
        $Continuous = $Action -eq "watch-approved-internal"
        $Coding = $Action -eq "run-approved-engineering"
        if ($Coding) {
            Write-Host "Single founder login: preview one approved engineering task, then confirm explicitly."
            Write-Host "No task POST without consent. No automatic repeat or GitHub write."
            & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login --require-engineering --interactive-apply --limit 1
            exit $LASTEXITCODE
        }
        Write-Host "Preview of authenticated, founder-approved internal brief tasks only."
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        if ($Continuous) {
            Write-Host "Watch will poll for at most 60 minutes / 10 approved tasks, only while this terminal is open."
            Write-Host "Every POST has a durable no-replay receipt under ~/.ago/approved_attempts."
        }
        $Confirmation = Read-Host "Authorize this bounded local AI work? Type EXECUTE_APPROVED_INTERNAL_TASKS"
        if ($Confirmation -cne "EXECUTE_APPROVED_INTERNAL_TASKS") {
            Write-Host "Execution cancelled. No tasks dispatched."
            exit 2
        }
        if ($Continuous) {
            & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login --watch-minutes 60 --limit 10 --interval-seconds 15 --apply --confirm EXECUTE_APPROVED_INTERNAL_TASKS
        }
        else {
            & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login --apply --confirm EXECUTE_APPROVED_INTERNAL_TASKS
        }
        exit $LASTEXITCODE
    }
    if ($Action -eq "export-candidate") {
        Write-Host "This exports code from an authenticated, completed AGO AI run for OFFLINE review only."
        $RunId = Read-Host "Exact completed AGO agent run ID (UUID)"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "A valid recorded run UUID is required."
        }
        $Confirmation = Read-Host "To export only, type EXPORT_APPROVED_AI_CANDIDATE"
        if ($Confirmation -cne "EXPORT_APPROVED_AI_CANDIDATE") {
            Write-Host "Export cancelled. No file created."
            exit 2
        }
        # Private AI-generated code is never written into the public Git checkout.
        $ExportDirectory = Join-Path $HOME ".ago\candidate_exports"
        if (-not (Test-Path -LiteralPath $ExportDirectory -PathType Container)) {
            New-Item -ItemType Directory -Path $ExportDirectory -Force | Out-Null
        }
        $OutputFile = Join-Path $ExportDirectory ("ago-run-" + $RunId + ".json")
        Write-Host "Private candidate destination: $OutputFile"
        & python ../../scripts/ago_pull_candidate.py --local-url "http://127.0.0.1:$Port" --run-id $RunId --output $OutputFile --apply --confirm EXPORT_APPROVED_AI_CANDIDATE
        exit $LASTEXITCODE
    }
    if ($Action -eq "test-exported-candidate") {
        Write-Host "Review private AI source before testing. Docker stays offline; human QA is separate."
        $RunId = Read-Host "Exact exported AGO agent run ID (UUID)"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "A valid run UUID is required."
        }
        $InputFile = Resolve-AGOExportReceipt -RunId $RunId
        $DeliveryRoot = Join-Path $HOME ".ago\delivery_runs"
        if (-not (Test-Path -LiteralPath $DeliveryRoot -PathType Container)) {
            New-Item -ItemType Directory -Path $DeliveryRoot -Force | Out-Null
        }
        $DeliveryId = [guid]::NewGuid().ToString("N")
        $Stage = Join-Path $DeliveryRoot ("stage-" + $DeliveryId)
        $Qa = Join-Path $DeliveryRoot ("qa-" + $DeliveryId + ".json")
        $PreviewText = (& python ../../scripts/ago_local_delivery_gate.py --input $InputFile --staged-directory $Stage --qa-output $Qa | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "AI code inspection failed. No Docker execution requested."
        }
        $Preview = $PreviewText | ConvertFrom-Json
        if ($Preview.input_kind -cne "board_record" -or $Preview.board_review_verified_from_local_receipt -ne $true) {
            throw "Full Board-approved source evidence is required for this command."
        }
        $Digest = $Preview.candidate_sha256
        if ($Digest -notmatch '^[0-9a-f]{64}$') {
            throw "Exact source digest missing."
        }
        Write-Host "Source review file: $InputFile"
        Write-Host "Candidate SHA256: $Digest"
        foreach ($File in $Preview.candidate_files) { Write-Host "  File: $File" }
        Write-Host "Inspect EVERY source and test file in the review JSON before confirming."
        $Confirmation = Read-Host "To run untrusted code in offline Docker, type TEST_REVIEWED_AI_CANDIDATE"
        if ($Confirmation -cne "TEST_REVIEWED_AI_CANDIDATE") {
            Write-Host "Testing cancelled. No candidate executed."
            exit 2
        }
        Write-Host "Docker execution stage (retain for a source-only repair if tests fail): $Stage"
        & python ../../scripts/ago_local_delivery_gate.py --input $InputFile --staged-directory $Stage --qa-output $Qa --expected-candidate-sha256 $Digest --apply --confirm STAGE_TEST_AND_PREPARE_QA
        if ($LASTEXITCODE -ne 0) {
            throw "Candidate did not pass isolated tests; no QA approval was issued."
        }
        Write-Host "Offline tests passed. QA review packet (not an approval): $Qa"
        exit 0
    }
    if ($Action -eq "review-tested-candidate") {
        Write-Host "Independent HUMAN QA: inspect actual generated files, acceptance criteria and Docker test evidence."
        Write-Host "This is NOT an automatic QA pass or GitHub release."
        $RunId = Read-Host "Exact exported AGO run ID (UUID)"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "A valid completed run UUID is required."
        }
        $ExportFile = Resolve-AGOExportReceipt -RunId $RunId
        $Stage = Read-Host "Exact existing PASSED Docker staged directory"
        $Qa = Read-Host "Exact existing pending QA packet JSON path"
        if (-not (Test-Path -LiteralPath $Stage -PathType Container) -or -not (Test-Path -LiteralPath $Qa -PathType Leaf)) {
            throw "The original staged test evidence and pending QA packet are required."
        }
        $Verdict = Read-Host "Independent human QA verdict: pass or fail"
        if ($Verdict -cnotin @("pass", "fail")) {
            throw "Explicit pass or fail required."
        }
        $Notes = Read-Host "Human review findings (at least 15 characters)"
        if (-not $Notes -or $Notes.Trim().Length -lt 15 -or $Notes.Trim().Length -gt 1200) {
            throw "Substantive independent review notes are required."
        }
        $Approve = Read-Host "To submit ONE signed AGO QA verdict, type INDEPENDENT_HUMAN_QA_DECISION"
        if ($Approve -cne "INDEPENDENT_HUMAN_QA_DECISION") {
            Write-Host "Review cancelled; no AGO QA decision submitted."
            exit 2
        }
        & python ../../scripts/ago_human_qa_handoff.py --local-url "http://127.0.0.1:$Port" --export $ExportFile --staged-directory $Stage --qa-packet $Qa --verdict $Verdict --notes $Notes --apply --confirm INDEPENDENT_HUMAN_QA_DECISION
        exit $LASTEXITCODE
    }
    if ($Action -eq "prepare-github-draft") {
        Write-Host "Generate an UNAPPROVED GitHub commit draft from an actual AGO human QA PASS."
        Write-Host "This does not change GitHub or verify the remote branch head."
        $RunId = Read-Host "Exact completed Board-cleared AGO run UUID"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "Recorded run UUID required."
        }
        $Source = Resolve-AGOExportReceipt -RunId $RunId
        $Stage = Read-Host "Original PASSING offline Docker stage path"
        $Qa = Read-Host "Exact pending local QA packet path"
        if (-not (Test-Path -LiteralPath $Stage -PathType Container) -or -not (Test-Path -LiteralPath $Qa -PathType Leaf)) {
            throw "Original source test stage and matching QA packet required."
        }
        $GithubProjectId = Read-Host "Existing AGO Github integration project UUID (not intake ID)"
        $ExpectedSha = Read-Host "Founder-reviewed 40-character develop HEAD SHA"
        $Message = Read-Host "Human-reviewed GitHub commit message"
        if ($GithubProjectId -notmatch '^[0-9a-fA-F-]{36}$' -or $ExpectedSha -notmatch '^[0-9a-f]{40}$' -or -not $Message) {
            throw "Exact GitHub project UUID, remote HEAD SHA, and message required."
        }
        $OperationId = [guid]::NewGuid().ToString()
        $Folder = Join-Path $HOME ".ago\delivery_runs"
        if (-not (Test-Path -LiteralPath $Folder -PathType Container)) {
            New-Item -ItemType Directory -Path $Folder -Force | Out-Null
        }
        $OutputFile = Join-Path $Folder ("github-draft-" + $OperationId + ".json")
        $Confirm = Read-Host "Prepare only a LOCAL QA-verified GitHub draft? Type PREPARE_VERIFIED_QA_GITHUB_DRAFT"
        if ($Confirm -cne "PREPARE_VERIFIED_QA_GITHUB_DRAFT") {
            Write-Host "Cancelled. No draft created."
            exit 2
        }
        & python ../../scripts/ago_prepare_github_handoff.py --local-url "http://127.0.0.1:$Port" --export $Source --staged-directory $Stage --qa-packet $Qa --output $OutputFile --github-project-id $GithubProjectId --operation-id $OperationId --expected-sha $ExpectedSha --message $Message --apply --confirm PREPARE_VERIFIED_QA_GITHUB_DRAFT
        if ($LASTEXITCODE -ne 0) {
            throw "Exact human QA or GitHub draft validation failed. No GitHub write."
        }
        Write-Host "LOCAL draft only. Governance review still required: $OutputFile"
        exit 0
    }
    if ($Action -eq "submit-github-proposal") {
        Write-Host "Founder submits a verified draft to AGO governance; GitHub remains unchanged."
        $RunId = Read-Host "Exact completed AGO AI run UUID"
        $OperationId = Read-Host "Exact saved GitHub draft operation UUID"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$' -or $OperationId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "Run and reviewed draft UUIDs are required."
        }
        $ExportFile = Resolve-AGOExportReceipt -RunId $RunId
        $DraftFile = Join-Path $HOME (".ago\delivery_runs\github-draft-" + $OperationId + ".json")
        $Stage = Read-Host "Original passing Docker stage directory"
        $Qa = Read-Host "Original independent QA handoff packet JSON"
        if (-not (Test-Path -LiteralPath $ExportFile -PathType Leaf) -or
            -not (Test-Path -LiteralPath $DraftFile -PathType Leaf) -or
            -not (Test-Path -LiteralPath $Stage -PathType Container) -or
            -not (Test-Path -LiteralPath $Qa -PathType Leaf)) {
            throw "Original exact QA-verified local source evidence required."
        }
        $Confirm = Read-Host "Submit ONE signed immutable proposal for independent review? Type SUBMIT_QA_VERIFIED_GITHUB_PROPOSAL"
        if ($Confirm -cne "SUBMIT_QA_VERIFIED_GITHUB_PROPOSAL") {
            Write-Host "Proposal cancelled; AGO and GitHub unchanged."
            exit 2
        }
        & python ../../scripts/ago_submit_github_proposal.py --local-url "http://127.0.0.1:$Port" --draft $DraftFile --export $ExportFile --staged-directory $Stage --qa-packet $Qa --apply --confirm SUBMIT_QA_VERIFIED_GITHUB_PROPOSAL
        exit $LASTEXITCODE
    }
    if ($Action -in @("apply-github-proposal", "execute-github-commit")) {
        $Execute = $Action -eq "execute-github-commit"
        Write-Host "AGO performs each GitHub delivery phase only after independent approval."
        $RunId = Read-Host "Exact original Board-cleared AGO run UUID"
        $OperationId = Read-Host "Exact QA-verified GitHub draft operation UUID"
        $ProposalId = Read-Host "Exact independently approved enterprise proposal UUID"
        if ($RunId -notmatch '^[0-9a-fA-F-]{36}$' -or
            $OperationId -notmatch '^[0-9a-fA-F-]{36}$' -or
            $ProposalId -notmatch '^[0-9a-fA-F-]{36}$') {
            throw "Three exact original run, operation and approval proposal UUIDs required."
        }
        $Export = Resolve-AGOExportReceipt -RunId $RunId
        $Draft = Join-Path $HOME (".ago\delivery_runs\github-draft-" + $OperationId + ".json")
        $Stage = Read-Host "Original passing offline Docker stage"
        $Qa = Read-Host "Original independent human QA packet"
        if (-not (Test-Path -LiteralPath $Export -PathType Leaf) -or
            -not (Test-Path -LiteralPath $Draft -PathType Leaf) -or
            -not (Test-Path -LiteralPath $Stage -PathType Container) -or
            -not (Test-Path -LiteralPath $Qa -PathType Leaf)) {
            throw "Original Board, source, Docker and human QA evidence must be preserved."
        }
        $Phase = if ($Execute) { "execute" } else { "apply" }
        $Confirmation = if ($Execute) { "EXECUTE_APPROVED_GITHUB_COMMIT" } else { "APPLY_INDEPENDENTLY_APPROVED_GITHUB_OPERATION" }
        Write-Host "Read-only preflight: $Phase (no GitHub write without separate explicit confirmation)"
        & python ../../scripts/ago_finalize_github_delivery.py --local-url "http://127.0.0.1:$Port" --action $Phase --draft $Draft --export $Export --staged-directory $Stage --qa-packet $Qa --proposal-id $ProposalId
        if ($LASTEXITCODE -ne 0) {
            throw "Signed source/independent approval preflight failed; no write requested."
        }
        if ($Execute) {
            Write-Host "WARNING: Next confirmation can make a REAL GitHub commit on private develop."
            Write-Host "No automatic PR, merge or release follows this operation."
        }
        $Accept = Read-Host "To authorize this EXACT step, type $Confirmation"
        if ($Accept -cne $Confirmation) {
            Write-Host "Cancelled. No mutating AGO request sent."
            exit 2
        }
        & python ../../scripts/ago_finalize_github_delivery.py --local-url "http://127.0.0.1:$Port" --action $Phase --draft $Draft --export $Export --staged-directory $Stage --qa-packet $Qa --proposal-id $ProposalId --apply --confirm $Confirmation
        exit $LASTEXITCODE
    }
    if ($Action -eq "safe-reconcile") {
        if (-not $env:AGO_MARKET_TENANT_ID) {
            throw "Set existing AGO_MARKET_TENANT_ID before local recovery."
        }
        & python ../../scripts/company_safe_reconcile.py --tenant-id $env:AGO_MARKET_TENANT_ID
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $Confirmation = Read-Host "To mark abandoned local runs FAILED without replay, type MARK_STALE_FAILED"
        if ($Confirmation -cne "MARK_STALE_FAILED") {
            Write-Host "Recovery cancelled. No state changed."
            exit 2
        }
        & python ../../scripts/company_safe_reconcile.py --tenant-id $env:AGO_MARKET_TENANT_ID --apply --confirm MARK_STALE_FAILED
        exit $LASTEXITCODE
    }
    if ($Action -eq "market-watch") {
        if (-not $env:AGO_MARKET_TENANT_ID) {
            throw "Set AGO_MARKET_TENANT_ID to your actual company UUID before launching market research."
        }
        & python ../../scripts/company_market_watch.py --tenant-id $env:AGO_MARKET_TENANT_ID --interval-seconds 3600
        exit $LASTEXITCODE
    }
    if ($Action -eq "serve") {
        # The retired M9 frontend no longer exists in the application package.
        # Founder starts this foreground server and decides when to shut it down.
        # Research is NEVER implicitly started by setting a tenant variable.
        # To run research, the founder launches 'market-watch' separately.
        # Visual Company Map: actual URL is printed only after Python preflight passes.
        # Old /console/ redirects to the visual Company Map; no duplicate UI.
        Write-Host "Checking local PostgreSQL, migrations, and secure settings (no secrets printed)."
        & python -m ago.local_ops doctor
        if ($LASTEXITCODE -ne 0) {
            Write-Host "AGO server NOT started; fix failed doctor checks above."
            exit $LASTEXITCODE
        }
        Write-Host "AGO local server only. Market watcher is not auto-started."
        & python -m ago.local_ops serve --port $Port
    }
    else {
        & python -m ago.local_ops $Action
    }
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
