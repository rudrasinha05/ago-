<#
.SYNOPSIS
Build, package, and launch AGO's actual founder Company Map in one terminal.
.DESCRIPTION
The detailed circular Company Map / Company Brain is the Next.js app under
apps/web, NOT the older /console/ admin interface. This helper keeps the
existing AGO_POSTGRES_DSN/session and does not change database contents,
perform migrations, create tenants or download Ollama models.
.EXAMPLE
.\scripts\ago-visual.ps1
#>
param(
    [ValidateRange(1024,65535)]
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$backend = Join-Path $root "apps\backend"
$web = Join-Path $root "apps\web"
$frontend = Join-Path $backend "ago\frontend\organization\index.html"

if (-not (Test-Path (Join-Path $web "components\company-map.jsx"))) {
    throw "Company Map source missing; check out the AGO develop branch."
}
if (-not (Test-Path (Join-Path $web "components\command-brain.jsx"))) {
    throw "Company Brain source missing; check out the AGO develop branch."
}
if ($env:AGO_ENVIRONMENT -and $env:AGO_ENVIRONMENT.ToLowerInvariant() -notin @("development","test","testing")) {
    throw "Visual launcher supports localhost development/testing only."
}
if (-not $env:AGO_POSTGRES_DSN) {
    throw "AGO_POSTGRES_DSN is not configured in this terminal. Use the existing verified local ago_test session; no new tenant is needed."
}
foreach ($commandName in @("python", "node", "npm.cmd")) {
    if (-not (Get-Command $commandName -ErrorAction SilentlyContinue)) {
        throw "$commandName was not found on PATH. Frontend requires Node.js 22+, npm and Python."
    }
}
$nodeVersion = (& node -p "Number(process.versions.node.split('.')[0])").Trim()
if ($LASTEXITCODE -ne 0 -or [int]$nodeVersion -lt 22) {
    throw "Node.js 22+ required for this Next.js frontend."
}
# Do not package new assets while an existing server is running with old routing.
$client = New-Object System.Net.Sockets.TcpClient
try {
    $connect = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
    $occupied = $connect.AsyncWaitHandle.WaitOne(500)
    if ($occupied -and $client.Connected) {
        throw "Port $Port is already occupied. Stop the old AGO server with Ctrl+C before rebuilding the Company Map."
    }
} finally {
    $client.Dispose()
}

Push-Location $backend
try {
    $doctorRaw = (& python -m ago.local_ops doctor | Out-String).Trim()
    if ($LASTEXITCODE -ne 0) { throw "AGO doctor could not run." }
    $diagnosis = $doctorRaw | ConvertFrom-Json
    Write-Host "Database/schema preflight: $doctorRaw"
    if (-not $diagnosis.ready) {
        throw "AGO doctor is not ready. The visual launcher never modifies the database."
    }
} finally {
    Pop-Location
}

Push-Location $root
try {
    Write-Host "AGO visual frontend: packaging the saved circular Company Map and Company Brain."
    if (-not (Test-Path (Join-Path $root "node_modules\next\package.json"))) {
        Write-Host "Installing pinned frontend dependencies from package-lock.json..."
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed; frontend was not packaged." }
    }
    & npm.cmd run build --workspace "@ago/web"
    if ($LASTEXITCODE -ne 0) { throw "Next.js Company Map build failed." }
    & python scripts/package_frontend.py
    if ($LASTEXITCODE -ne 0) { throw "Next.js frontend packaging failed." }
    if (-not (Test-Path -LiteralPath $frontend -PathType Leaf)) {
        throw "Packaged Company Map route missing. Backend was not started."
    }
    Write-Host ""
    Write-Host "AGO VISUAL WORKSPACE READY"
    Write-Host "Open http://127.0.0.1:$Port/workspace/organization/"
    Write-Host "  Circular organization map | Company Brain | Board seats"
    Write-Host "  Activity links and counters depend on real task/event records."
    Write-Host "Sign in with your existing AGO organization ID and founder credentials."
    Write-Host "Starting the same-origin AGO API + visual frontend (Ctrl+C to stop)."
    & "$PSScriptRoot\ago.ps1" serve -Port $Port
    if ($LASTEXITCODE -ne 0) { throw "AGO server failed to start." }
} finally {
    Pop-Location
}
