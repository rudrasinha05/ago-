# Verify the already-running AGO visual server and all first-party routes.
# Read-only, localhost, never starts/stops or modifies server/database.
param([ValidateRange(1024,65535)][int]$Port=8000)
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
& python (Join-Path $root "scripts\\ago_route_audit.py") --port $Port
exit $LASTEXITCODE
