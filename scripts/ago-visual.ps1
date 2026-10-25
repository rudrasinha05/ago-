<#
.SYNOPSIS
Build, package, and launch AGO's actual founder Company Map in one terminal.
.DESCRIPTION
The detailed circular Company Map / Company Brain is the Next.js app under
apps/web; the retired M9 console code is no longer shipped. This helper reuses the session AGO_POSTGRES_DSN or securely prompts for the
existing local ago_test password in a fresh terminal. It never changes database contents,
perform migrations, create tenants or download Ollama models.
.EXAMPLE
.\scripts\ago-visual.ps1
.\scripts\ago-visual.ps1 -Engineering -Model qwen2.5-coder:1.5b
#>
param(
    [ValidateRange(1024,65535)]
    [int]$Port = 8000,
    [switch]$Engineering,
    [ValidateSet("qwen2.5:3b", "qwen2.5:1.5b", "qwen2.5-coder:1.5b")]
    [string]$Model = "qwen2.5-coder:1.5b"
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
    # PowerShell environment variables are process-scoped. A new VS Code
    # terminal does not inherit the DSN set by a previous migration session.
    # Only reconnect to the known historical localhost database; never create
    # a database, tenant, password file, Windows-wide variable or migration.
    Write-Host "New terminal detected: reconnecting to the existing local ago_test database."
    $securePassword = Read-Host "PostgreSQL password for postgres (hidden)" -AsSecureString
    $password = [System.Net.NetworkCredential]::new("", $securePassword).Password
    if ([string]::IsNullOrEmpty($password)) {
        throw "No PostgreSQL password entered. Nothing was changed."
    }
    $encodedPassword = [Uri]::EscapeDataString($password)
    $env:AGO_POSTGRES_DSN = "postgresql://postgres:${encodedPassword}@127.0.0.1:5432/ago_test"
    Remove-Variable password, securePassword, encodedPassword -ErrorAction SilentlyContinue
    Write-Host "Existing local ago_test selected for this terminal only."
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

# Revert opt-in model flags when this foreground operator process stops.
$ModelFlagNames = @(
    "AGO_LLM_PROVIDER", "AGO_ENABLE_LOCAL_MODELS", "AGO_LLM_MODEL",
    "AGO_LOCAL_COMPANY_CHAIN", "AGO_LOCAL_FULL_BOARD_REVIEW",
    "AGO_LOCAL_ENGINEERING_CANDIDATES"
)
$PreviousModelFlags = @{}
Push-Location $root
try {
    Write-Host "AGO visual frontend: packaging the saved circular Company Map and Company Brain."
    # An existing node_modules directory is not proof that its packages match Git.
    # In particular, a stale local Next.js can survive a git pull unchanged.
    $lockPath = Join-Path $root "package-lock.json"
    $webPackagePath = Join-Path $web "package.json"
    $installedNextPath = Join-Path $root "node_modules\next\package.json"
    if (-not (Test-Path -LiteralPath $lockPath -PathType Leaf)) {
        throw "package-lock.json missing. Refusing an unpinned frontend install."
    }
    $expectedNext = (Get-Content -LiteralPath $webPackagePath -Raw | ConvertFrom-Json).dependencies.next
    $lockData = Get-Content -LiteralPath $lockPath -Raw | ConvertFrom-Json
    $lockedNextEntry = $lockData.packages.PSObject.Properties["node_modules/next"]
    $lockedNext = if ($lockedNextEntry) { $lockedNextEntry.Value.version } else { $null }
    if ([string]::IsNullOrWhiteSpace($expectedNext) -or $expectedNext -cne $lockedNext) {
        throw "Next.js version in apps/web/package.json does not match package-lock.json. Refusing to install."
    }
    $installedNext = $null
    if (Test-Path -LiteralPath $installedNextPath -PathType Leaf) {
        try {
            $installedNext = (Get-Content -LiteralPath $installedNextPath -Raw | ConvertFrom-Json).version
        } catch {
            Write-Host "Installed Next.js manifest is invalid; restoring pinned dependencies."
        }
    }
    if ($installedNext -cne $lockedNext) {
        Write-Host "Next.js installation is missing or outdated (installed: $installedNext; pinned: $lockedNext)."
        Write-Host "Restoring pinned frontend dependencies from package-lock.json with npm ci..."
        & npm.cmd ci
        if ($LASTEXITCODE -ne 0) { throw "npm ci failed; frontend was not packaged." }
        if (-not (Test-Path -LiteralPath $installedNextPath -PathType Leaf)) {
            throw "npm ci completed without the pinned Next.js package."
        }
        $installedNext = (Get-Content -LiteralPath $installedNextPath -Raw | ConvertFrom-Json).version
        if ($installedNext -cne $lockedNext) {
            throw "Installed Next.js still does not match package-lock.json after npm ci."
        }
    }
    Write-Host "Next.js dependency verified: $installedNext (matches Git lockfile)."
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
    if ($Engineering) {
        if ($env:AGO_ENABLE_PAID_MODELS -eq "true") {
            throw "Disable paid providers before local engineering mode."
        }
        # Only validate an already-installed localhost model. Do not launch,
        # download, or connect a model to a cloud provider.
        & "$PSScriptRoot\ago-ollama-check.ps1" -Model $Model
        if ($LASTEXITCODE -ne 0) {
            throw "Local engineering requires an already-installed responsive Ollama model."
        }
        foreach ($Flag in $ModelFlagNames) {
            $PreviousModelFlags[$Flag] = [Environment]::GetEnvironmentVariable($Flag, "Process")
        }
        $env:AGO_LLM_PROVIDER = "ollama_local"
        $env:AGO_ENABLE_LOCAL_MODELS = "true"
        $env:AGO_LLM_MODEL = $Model
        $env:AGO_LOCAL_COMPANY_CHAIN = "true"
        $env:AGO_LOCAL_FULL_BOARD_REVIEW = "true"
        $env:AGO_LOCAL_ENGINEERING_CANDIDATES = "true"
        Write-Host "Local engineering ENABLED for this foreground AGO session only."
        Write-Host "Seven real appointed AI employees and approved project tasks are required."
        Write-Host "No autonomous GitHub write, deployment, or QA approval is enabled."
    }
    Write-Host "Starting the same-origin AGO API + visual frontend (Ctrl+C to stop)."
    & "$PSScriptRoot\ago.ps1" serve -Port $Port
    if ($LASTEXITCODE -ne 0) { throw "AGO server failed to start." }
} finally {
    if ($PreviousModelFlags.Count -gt 0) {
        foreach ($Flag in $ModelFlagNames) {
            [Environment]::SetEnvironmentVariable(
                $Flag, $PreviousModelFlags[$Flag], "Process"
            )
        }
    }
    Pop-Location
}
