# Guarded local historical AGO schema upgrade (never touches ago_dev).
# Run from a PowerShell terminal: .\scripts\ago-upgrade-historical-db.ps1
param(
    [string]$DbUser = "postgres",
    [string]$PostgresBin = "C:\Program Files\PostgreSQL\bin"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "apps\backend"
$helper = Join-Path $root "scripts\ago_update_local_schema.py"
if (-not (Test-Path (Join-Path $PostgresBin "pg_dump.exe"))) {
    throw "pg_dump.exe not found. Supply -PostgresBin; no SQL was changed."
}
if (-not (Test-Path $helper)) { throw "Upgrade helper missing; pull develop." }
if ($env:AGO_ENVIRONMENT -and $env:AGO_ENVIRONMENT -ne "development") {
    throw "Only development environment is supported."
}
$env:AGO_ENVIRONMENT = "development"
$secure = Read-Host "PostgreSQL password for $DbUser" -AsSecureString
$plain = [System.Net.NetworkCredential]::new("", $secure).Password
if ([string]::IsNullOrEmpty($plain)) {
    throw "No PostgreSQL password was entered. The upgrade is cancelled without changes."
}
$encodedUser = [Uri]::EscapeDataString($DbUser)
$encodedPass = [Uri]::EscapeDataString($plain)
$env:AGO_POSTGRES_DSN = "postgresql://${encodedUser}:${encodedPass}@127.0.0.1:5432/ago_test"
Remove-Variable secure, plain, encodedPass -ErrorAction SilentlyContinue
$oldPath = $env:PATH
$env:PATH = "$PostgresBin;$oldPath"
Push-Location $backend
try {
    Write-Host "1) Read-only plan for ago_test (no other database changes)"
    & python $helper
    if ($LASTEXITCODE -ne 0) {
        throw "Preflight blocked. No migration requested."
    }
    Write-Host ""
    Write-Host "2) Backup and upgrade ago_test ONLY; ago_dev and postgres are untouched."
    $confirm = Read-Host "Type UPDATE_HISTORICAL_AGO_TEST to authorize"
    if ($confirm -cne "UPDATE_HISTORICAL_AGO_TEST") {
        Write-Host "Cancelled. No migration requested."
        return
    }
    & python $helper --apply --confirm UPDATE_HISTORICAL_AGO_TEST
    if ($LASTEXITCODE -ne 0) {
        throw "Upgrade blocked or failed. Check safe status and verified backup before any retry."
    }
    Write-Host "3) AGO doctor; ready must be true before serve"
    & python -m ago.local_ops doctor
    if ($LASTEXITCODE -ne 0) {
        throw "Doctor process failed. Do not start AGO."
    }
    Write-Host "The selected session's AGO_POSTGRES_DSN now points to local ago_test."
} finally {
    Pop-Location
    $env:PATH = $oldPath
}
