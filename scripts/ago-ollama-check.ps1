<#
.SYNOPSIS
Read-only, founder-started AGO Ollama localhost/model check.
Does NOT install, pull, start or auto-enable Ollama or wake the laptop.
#>
param(
    [ValidateSet("qwen2.5:3b", "qwen2.5:1.5b")]
    [string]$Model = "qwen2.5:3b"
)

$ErrorActionPreference = "Stop"
$endpoint = "http://127.0.0.1:11434/api/tags"
try {
    $status = Invoke-RestMethod -Method Get -Uri $endpoint -TimeoutSec 5
} catch {
    Write-Error "AGO local Ollama is not responding at 127.0.0.1:11434. Start it yourself when you want local AI."
    exit 2
}
$found = $false
foreach ($entry in $status.models) {
    if ($entry.name -eq $Model) { $found = $true; break }
}
if (-not $found) {
    Write-Warning "Requested $Model is not installed locally. If you choose, manually run: ollama pull $Model"
    exit 3
}
Write-Host "AGO Ollama READY: $Model, localhost only. No model inference launched."
exit 0
