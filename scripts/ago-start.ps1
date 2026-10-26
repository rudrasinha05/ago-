<#
.SYNOPSIS
Start the existing AGO Company Map and local Qwen engineering with one command.
.EXAMPLE
.\scripts\ago-start.ps1
.\scripts\ago-start.ps1 -Update
.\scripts\ago-start.ps1 -SoloFounder
.DESCRIPTION
Safe local-only launcher. Existing company, approvals, PostgreSQL and repository
changes are preserved. No migrations, git stashes/resets, Docker image pulls,
paid providers, tenant provisioning, background watchers or GitHub writes.
-Update fast-forwards only a CLEAN develop checkout; when locally modified it
skips sync rather than refusing to launch AGO.
#>
param(
    [switch]$Update,
    [switch]$SoloFounder,
    [ValidateSet("qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5-coder:1.5b")]
    [string]$Model = "qwen2.5-coder:1.5b",
    [ValidateRange(1024,65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

if ($env:AGO_ENVIRONMENT -and
    $env:AGO_ENVIRONMENT.ToLowerInvariant() -notin @("development", "test", "testing")) {
    throw "AGO Start is only available for local development/test. No production mode."
}
if (-not (Test-Path -LiteralPath (Join-Path $Root "apps\backend\ago\local_ops.py") -PathType Leaf)) {
    throw "Open the existing AGO repository; the expected backend is missing."
}
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    throw "Git is missing from PATH. Existing AGO checkout is required."
}

Push-Location $Root
try {
    $Branch = (& git branch --show-current).Trim()
    if ($LASTEXITCODE -ne 0 -or $Branch -cne "develop") {
        throw "AGO runs from your existing develop checkout. No automatic branch switching."
    }
    $LocalChanges = @(& git status --porcelain)
    if ($LASTEXITCODE -ne 0) {
        throw "Cannot safely inspect local files. No Git operation performed."
    }
    if ($LocalChanges.Count -gt 0) {
        Write-Host "Local Git changes preserved. Startup does NOT require git stash or reset."
    }
    if ($Update) {
        if ($LocalChanges.Count -gt 0) {
            Write-Warning "Update skipped: modified files are preserved; launching existing AGO checkout."
        } else {
            Write-Host "Updating clean develop checkout (fast-forward only)..."
            & "$PSScriptRoot\ago-sync.ps1"
            if ($LASTEXITCODE -ne 0) {
                throw "Git fast-forward failed; no force/reset was attempted."
            }
        }
    } else {
        Write-Host "Starting installed AGO checkout. Git update is optional (-Update)."
    }

    # PowerShell's PATH may omit a valid user-scoped Docker Desktop install.
    # Fix only THIS launcher process, never the Windows user/system PATH.
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        $Locations = @(
            (Join-Path $env:LOCALAPPDATA "Programs\DockerDesktop\resources\bin"),
            (Join-Path $env:ProgramFiles "Docker\Docker\resources\bin")
        )
        foreach ($Location in $Locations) {
            if ($Location -and (Test-Path -LiteralPath (Join-Path $Location "docker.exe") -PathType Leaf)) {
                $env:Path += [IO.Path]::PathSeparator + $Location
                Write-Host "Local Docker CLI detected; PATH fixed for this session."
                break
            }
        }
    }
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Warning "Docker CLI not found. AGO UI can start; Docker QA will remain unavailable."
    }

    $Previous = @{
        AGO_ENVIRONMENT = [Environment]::GetEnvironmentVariable("AGO_ENVIRONMENT", "Process")
        AGO_ENABLE_PAID_MODELS = [Environment]::GetEnvironmentVariable("AGO_ENABLE_PAID_MODELS", "Process")
        AGO_FOUNDER_SOLO_APPROVAL = [Environment]::GetEnvironmentVariable("AGO_FOUNDER_SOLO_APPROVAL", "Process")
    }
    try {
        if (-not $env:AGO_ENVIRONMENT) { $env:AGO_ENVIRONMENT = "development" }
        $env:AGO_ENABLE_PAID_MODELS = "false"
        if ($SoloFounder) {
            Write-Host "Opt-in sole-Founder LOCAL approval requested; AGO verifies eligibility per action."
            $env:AGO_FOUNDER_SOLO_APPROVAL = "true"
        }
        Write-Host "AGO: One startup. Same existing company. Local Ollama. No paid API."
        & "$PSScriptRoot\ago-visual.ps1" -Engineering -Model $Model -Port $Port
        if ($LASTEXITCODE -ne 0) { throw "AGO visual startup failed; inspect the safe preflight message above." }
    } finally {
        foreach ($Name in $Previous.Keys) {
            [Environment]::SetEnvironmentVariable($Name, $Previous[$Name], "Process")
        }
    }
} finally {
    Pop-Location
}
