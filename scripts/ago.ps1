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
#>
param(
    [ValidateSet("doctor", "tenants", "init", "init-solo", "serve", "migrate", "test", "market-watch", "company-pulse", "safe-reconcile", "run-approved-internal")]
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
    if ($Action -eq "run-approved-internal") {
        Write-Host "Dry run of signed, founder-controlled, approved internal brief tasks."
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port"
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        $Confirmation = Read-Host "Run up to 3 individually approved internal tasks? Type EXECUTE_APPROVED_INTERNAL_TASKS"
        if ($Confirmation -cne "EXECUTE_APPROVED_INTERNAL_TASKS") {
            Write-Host "Execution cancelled. No tasks dispatched."
            exit 2
        }
        & python ../../scripts/local_approved_agent_batch.py --local-url "http://127.0.0.1:$Port" --apply --confirm EXECUTE_APPROVED_INTERNAL_TASKS
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
