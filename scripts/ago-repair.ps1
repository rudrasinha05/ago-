<#
.SYNOPSIS
AGO bounded local repair and retest of an actual failed Docker candidate.
.EXAMPLE
.\scripts\ago-repair.ps1 -Mode propose -FailedStage "$HOME\.ago\delivery_runs\stage-..."
.\scripts\ago-repair.ps1 -Mode retest -FailedStage "$HOME\.ago\delivery_runs\stage-..." -Proposal "$HOME\.ago\delivery_runs\repair-....json"
#>
param(
    [ValidateSet("preview", "propose", "retest")]
    [string]$Mode = "preview",
    [Parameter(Mandatory=$true)]
    [string]$FailedStage,
    [string]$Proposal,
    [ValidateSet("qwen2.5-coder:1.5b", "qwen2.5:1.5b", "qwen2.5:3b")]
    [string]$Model = "qwen2.5-coder:1.5b"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Backend = Join-Path $RepoRoot "apps\backend"
$PrivateRoot = Join-Path $HOME ".ago\delivery_runs"
if (-not (Test-Path -LiteralPath $FailedStage -PathType Container)) {
    throw "An existing failed Docker staged directory is required."
}
$FailedStage = (Resolve-Path -LiteralPath $FailedStage).Path
# Never accept arbitrary generated code files as a substitute for the original
# immutable failed stage; the Python verifier checks every digest and receipt.
if (-not (Test-Path -LiteralPath (Join-Path $FailedStage "AGO_TEST_RECEIPT.json") -PathType Leaf)) {
    throw "A real failed test receipt is required."
}
if (-not (Test-Path -LiteralPath $PrivateRoot -PathType Container)) {
    New-Item -Path $PrivateRoot -ItemType Directory -Force | Out-Null
}
$RunId = [guid]::NewGuid().ToString("N")
$Output = Join-Path $PrivateRoot ("repair-" + $RunId + ".json")
$NewStage = Join-Path $PrivateRoot ("retest-" + $RunId)
$Qa = Join-Path $PrivateRoot ("qa-retest-" + $RunId + ".json")

Push-Location $Backend
try {
    if ($Mode -eq "preview" -or $Mode -eq "propose") {
        Write-Host "Original failed stage: $FailedStage"
        & python ../../scripts/ago_local_repair_proposal.py --staged-directory $FailedStage --output $Output
        if ($LASTEXITCODE -ne 0) {
            throw "Original staged source / Docker failure receipt did not verify."
        }
        if ($Mode -eq "preview") {
            Write-Host "Read-only. No model invocation, code write or test execution."
            exit 0
        }
        & "$PSScriptRoot\ago-ollama-check.ps1" -Model $Model
        if ($LASTEXITCODE -ne 0) {
            throw "Already-installed local Ollama is required; no cloud fallback."
        }
        $Answer = Read-Host "Run ONE local source-only repair inference? Type PROPOSE_ONE_LOCAL_SOURCE_REPAIR"
        if ($Answer -cne "PROPOSE_ONE_LOCAL_SOURCE_REPAIR") {
            Write-Host "Repair cancelled without invoking the model."
            exit 2
        }
        $FlagNames = @("AGO_LLM_PROVIDER", "AGO_ENABLE_LOCAL_MODELS", "AGO_LOCAL_REPAIR_PROPOSALS", "AGO_LLM_MODEL")
        $Saved = @{}
        foreach ($Name in $FlagNames) {
            $Saved[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
        }
        try {
            $env:AGO_LLM_PROVIDER = "ollama_local"
            $env:AGO_ENABLE_LOCAL_MODELS = "true"
            $env:AGO_LOCAL_REPAIR_PROPOSALS = "true"
            $env:AGO_LLM_MODEL = $Model
            & python ../../scripts/ago_local_repair_proposal.py --staged-directory $FailedStage --output $Output --apply --confirm PROPOSE_ONE_LOCAL_SOURCE_REPAIR
            if ($LASTEXITCODE -ne 0) {
                throw "One model proposal failed, original source and test evidence unchanged."
            }
            Write-Host "UNAPPROVED repaired SOURCE proposal: $Output"
            Write-Host "Review the full proposal source; tests have NOT been executed."
        }
        finally {
            foreach ($Name in $FlagNames) {
                [Environment]::SetEnvironmentVariable($Name, $Saved[$Name], "Process")
            }
        }
        exit 0
    }
    if ($Mode -eq "retest") {
        if (-not $Proposal -or -not (Test-Path -LiteralPath $Proposal -PathType Leaf)) {
            throw "Existing unapproved source-only repair proposal required."
        }
        $Proposal = (Resolve-Path -LiteralPath $Proposal).Path
        $PreviewRaw = (& python ../../scripts/ago_local_delivery_gate.py --input $Proposal --repair-from $FailedStage --staged-directory $NewStage --qa-output $Qa | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) {
            throw "Repair lineage or source/test byte preservation failed."
        }
        $Preview = $PreviewRaw | ConvertFrom-Json
        if ($Preview.input_kind -cne "repair_pending_retest" -or $Preview.repair_source_lineage_checked -ne $true) {
            throw "Only source-only repairs preserving original failed tests may be retested."
        }
        $Digest = $Preview.candidate_sha256
        if ($Digest -notmatch '^[0-9a-f]{64}$') {
            throw "Reviewed repaired candidate digest missing."
        }
        Write-Host "Repaired source SHA256: $Digest"
        Write-Host "Original failed evidence: $FailedStage"
        Write-Host "Review the entire repair proposal, unchanged tests and acceptance checks."
        $Answer = Read-Host "Execute ONE isolated Docker retest? Type RETEST_REVIEWED_SOURCE_REPAIR"
        if ($Answer -cne "RETEST_REVIEWED_SOURCE_REPAIR") {
            Write-Host "Retest cancelled without executing code."
            exit 2
        }
        Write-Host "Re-test stage (retain even if test fails): $NewStage"
        & python ../../scripts/ago_local_delivery_gate.py --input $Proposal --repair-from $FailedStage --staged-directory $NewStage --qa-output $Qa --expected-candidate-sha256 $Digest --apply --confirm STAGE_TEST_AND_PREPARE_QA
        if ($LASTEXITCODE -ne 0) {
            throw "Repaired source failed offline Docker retest; no QA approval."
        }
        Write-Host "Test passed. INDEPENDENT HUMAN QA PENDING: $Qa"
        exit 0
    }
}
finally {
    Pop-Location
}
