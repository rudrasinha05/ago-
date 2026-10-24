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
.\scripts\ago.ps1 watch-approved-internal  # up to 60 minutes or 10 tasks; Ctrl+C stops
.\scripts\ago.ps1 export-candidate  # exact completed Board-cleared AI run -> new local source review
#>
param(
    [ValidateSet("doctor", "tenants", "init", "init-solo", "serve", "migrate", "test", "market-watch", "company-pulse", "safe-reconcile", "run-approved-internal", "run-approved-engineering", "watch-approved-internal", "export-candidate")]
    [string]$Action = "doctor",
    [ValidateRange(1024,65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendPath = Join-Path $RepoRoot "apps\backend"
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
    if ($Action -in @("run-approved-internal", "run-approved-engineering", "watch-approved-internal")) {
        $Continuous = $Action -eq "watch-approved-internal"
        $Coding = $Action -eq "run-approved-engineering"
        $CodingCheck = @()
        if ($Coding) { $CodingCheck += "--require-engineering" }
        Write-Host "Preview of authenticated, founder-approved internal brief tasks only."
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login @CodingCheck
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
            & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --login @CodingCheck --apply --confirm EXECUTE_APPROVED_INTERNAL_TASKS
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
        Write-Host "AGO local server only. Market watcher is not auto-started."
        $VisualRoute = Join-Path $BackendPath "ago\frontend\organization\index.html"
        if (Test-Path -LiteralPath $VisualRoute -PathType Leaf) {
            Write-Host "Visual Company Map: http://127.0.0.1:$Port/workspace/organization/"
        }
        else {
            Write-Host "Company Map React frontend is not packaged. From repo root use .\\scripts\\ago-visual.ps1"
            Write-Host "Old /console/ redirects to the visual Company Map; no duplicate UI."
        }
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
