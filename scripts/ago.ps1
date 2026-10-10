<#
.SYNOPSIS
AGO local Windows operator console (never fetches Git or touches production).
.EXAMPLE
.\scripts\ago.ps1 doctor
.\scripts\ago.ps1 init
.\scripts\ago.ps1 serve
.\scripts\ago.ps1 migrate
#>
param(
    [ValidateSet("doctor", "tenants", "init", "serve", "migrate", "test")]
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
    if ($Action -eq "serve") {
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
