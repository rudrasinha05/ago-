<#
.SYNOPSIS
AGO independently governed 4-phase DRAFT PR workflow (no merge or release).
.EXAMPLE
.\scripts\ago-pr.ps1 -Phase prepare
.\scripts\ago-pr.ps1 -Phase submit
.\scripts\ago-pr.ps1 -Phase apply
.\scripts\ago-pr.ps1 -Phase execute
#>
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("prepare", "submit", "apply", "execute")]
    [string]$Phase,
    [ValidateRange(1,65535)]
    [int]$Port = 8000
)
$ErrorActionPreference = "Stop"
$RunId = Read-Host "Exact ORIGINAL AGO Board-cleared run UUID"
$CommitId = Read-Host "Original approved GitHub COMMIT draft operation UUID"
$CommitProposal = Read-Host "Original independently approved COMMIT proposal UUID"
if ($RunId -notmatch '^[0-9a-fA-F-]{36}$' -or
    $CommitId -notmatch '^[0-9a-fA-F-]{36}$' -or
    $CommitProposal -notmatch '^[0-9a-fA-F-]{36}$') {
    throw "Original run, commit operation and commit approval proposal UUID required."
}
$Export = Join-Path $HOME (".ago\candidate_exports\ago-run-" + $RunId + ".json")
$CommitDraft = Join-Path $HOME (".ago\delivery_runs\github-draft-" + $CommitId + ".json")
$Stage = Read-Host "Original successful offline Docker stage path"
$QA = Read-Host "Matching independently reviewed QA packet path"
if (-not (Test-Path -LiteralPath $Export -PathType Leaf) -or
    -not (Test-Path -LiteralPath $CommitDraft -PathType Leaf) -or
    -not (Test-Path -LiteralPath $Stage -PathType Container) -or
    -not (Test-Path -LiteralPath $QA -PathType Leaf)) {
    throw "Real original source, signed human QA and committed-source draft required."
}
if ($Phase -eq "prepare") {
    $PrId = [guid]::NewGuid().ToString()
} else {
    $PrId = Read-Host "Exact saved DRAFT PR operation UUID"
    if ($PrId -notmatch '^[0-9a-fA-F-]{36}$') {
        throw "Original draft PR operation UUID required."
    }
}
$PrDraft = Join-Path $HOME (".ago\delivery_runs\pr-draft-" + $PrId + ".json")
$Args = @(
    "--phase", $Phase,
    "--local-url", "http://127.0.0.1:$Port",
    "--commit-draft", $CommitDraft,
    "--export", $Export,
    "--stage", $Stage,
    "--qa", $QA,
    "--pr-draft", $PrDraft,
    "--commit-proposal", $CommitProposal
)
$Confirmation = ""
switch ($Phase) {
    "prepare" {
        $Title = Read-Host "Human-reviewed draft PR title"
        $Body = Read-Host "Human-reviewed PR description (not release approval)"
        $Names = Read-Host "Exact required CI workflow names, separated by commas"
        $Checks = @($Names.Split(",") | ForEach-Object { $_.Trim() })
        if (-not $Title -or -not $Body -or $Checks.Count -lt 1 -or
            @($Checks | Where-Object { -not $_ }).Count -gt 0 -or
            @($Checks | Select-Object -Unique).Count -ne $Checks.Count) {
            throw "Human PR title, description and unique CI workflow names required."
        }
        $Args += @("--operation-id", $PrId, "--title", $Title, "--body", $Body)
        foreach ($Check in $Checks) { $Args += @("--required-check", $Check) }
        $Confirmation = "PREPARE_VERIFIED_DRAFT_PR"
    }
    "submit" { $Confirmation = "SUBMIT_VERIFIED_DRAFT_PR" }
    "apply" {
        $Proposal = Read-Host "Exact independently approved DRAFT PR proposal UUID"
        $Args += @("--pr-proposal", $Proposal)
        $Confirmation = "APPLY_APPROVED_DRAFT_PR"
    }
    "execute" {
        $Proposal = Read-Host "Exact independently approved DRAFT PR proposal UUID"
        $Args += @("--pr-proposal", $Proposal)
        $Confirmation = "CREATE_APPROVED_DRAFT_PR"
        Write-Host "WARNING: This may create a real DRAFT PR on your PRIVATE GitHub repository."
        Write-Host "AGO will not merge main, deploy, publish or release your project."
    }
}
$Backend = Join-Path (Split-Path -Parent $PSScriptRoot) "apps\backend"
Push-Location $Backend
try {
    Write-Host "Readonly signed preflight: $Phase (no GitHub writes)"
    & python ../../scripts/ago_draft_pull_request.py @Args
    if ($LASTEXITCODE -ne 0) {
        throw "Real signed source, committed HEAD, required CI or governance gate blocked."
    }
    Write-Host "Candidate PR operation UUID: $PrId"
    if ($Phase -eq "prepare") { Write-Host "Private PR draft location: $PrDraft" }
    $Consent = Read-Host "Authorize EXACTLY this phase? Type $Confirmation"
    if ($Consent -cne $Confirmation) {
        Write-Host "Cancelled; no mutating request performed."
        exit 2
    }
    & python ../../scripts/ago_draft_pull_request.py @Args --apply --confirm $Confirmation
    exit $LASTEXITCODE
}
finally {
    Pop-Location
}
