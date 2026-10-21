<#
.SYNOPSIS
Safely fast-forward the existing AGO develop checkout from the VS Code terminal.
Never resets branches, deletes files, runs migrations or touches a live database.
.EXAMPLE
.\scripts\ago-sync.ps1
#>
$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Push-Location $Root
try {
    if (-not (Test-Path '.git')) { throw 'Not an AGO Git checkout.' }
    $current = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $current -cne 'develop') {
        throw 'Open existing develop branch first. No automatic branch switch.'
    }
    $dirty = & git status --porcelain
    if ($LASTEXITCODE -ne 0 -or $dirty) {
        throw 'Working tree has local changes. Commit/stash manually before pulling.'
    }
    & git fetch origin develop
    if ($LASTEXITCODE -ne 0) { throw 'Fetch failed: checkout not modified.' }
    & git pull --ff-only origin develop
    if ($LASTEXITCODE -ne 0) { throw 'Cannot fast-forward. No force reset performed.' }
    $sha = (& git rev-parse --short HEAD).Trim()
    Write-Host "AGO develop synced to $sha. Local PostgreSQL untouched."
    Write-Host 'To enable local founder-only approvals in THIS server terminal:'
    Write-Host '  $env:AGO_FOUNDER_SOLO_APPROVAL = "true"'
    Write-Host '  .\scripts\ago.ps1 doctor'
    Write-Host '  .\scripts\ago.ps1 serve'
} finally {
    Pop-Location
}
