# Read-only local PostgreSQL comparison for AGO founder.
# Uses the existing psql.exe; never migrates, updates, creates, or drops data.
# Usage: .\scripts\ago-compare-local-databases.ps1
param(
    [string]$PsqlPath = "C:\Program Files\PostgreSQL\bin\psql.exe",
    [string]$DbUser = "postgres"
)
$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$sqlDirectory = Join-Path $root "deploy\sql"
if (-not (Test-Path -LiteralPath $PsqlPath -PathType Leaf)) {
    $detected = Get-Command psql -ErrorAction SilentlyContinue
    if ($null -eq $detected) { throw "psql.exe not found. Supply -PsqlPath." }
    $PsqlPath = $detected.Source
}
if (-not (Test-Path -LiteralPath $sqlDirectory -PathType Container)) {
    throw "AGO deploy/sql directory not found."
}

$expected = @{}
foreach ($file in (Get-ChildItem -LiteralPath $sqlDirectory -Filter "*.sql" -File)) {
    $expected[$file.Name] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
}
if ($expected.Count -lt 1) { throw "No SQL migrations found: cannot compare." }

function Invoke-ReadOnlySql {
    param([string]$Database, [string]$Sql)
    # Fixed local endpoint and explicit SQL SELECT only; PGOPTIONS adds DB-side guard.
    $lines = @(& $PsqlPath -h 127.0.0.1 -p 5432 -U $DbUser -d $Database -X -q -A -t -w -v ON_ERROR_STOP=1 -c $Sql 2>&1)
    if ($LASTEXITCODE -ne 0) {
        throw "Read-only query failed for $Database (psql exit $LASTEXITCODE). Verify the PostgreSQL credentials and local database."
    }
    foreach ($line in $lines) {
        $value = [string]$line
        if ($value.Trim().Length -gt 0) { Write-Output $value.Trim() }
    }
}
function Get-Cell {
    param([string]$Database, [string]$Sql)
    $rows = @(Invoke-ReadOnlySql -Database $Database -Sql $Sql)
    if ($rows.Count -eq 0) { return "" }
    return [string]$rows[0]
}

$tableNames = @(
    "ago_tenants", "ago_users", "ago_employees", "ago_strategy_plans",
    "ago_founder_intakes", "ago_governed_tasks", "ago_agent_runs",
    "ago_approval_requests"
)
$databases = @("ago_test", "ago_dev", "postgres")
$oldPgPassword = [Environment]::GetEnvironmentVariable("PGPASSWORD", "Process")
$oldPgOptions = [Environment]::GetEnvironmentVariable("PGOPTIONS", "Process")
$securePassword = Read-Host "Local PostgreSQL password for $DbUser" -AsSecureString
try {
    $env:PGPASSWORD = [System.Net.NetworkCredential]::new("", $securePassword).Password
    $env:PGOPTIONS = "-c default_transaction_read_only=on"
    $summaries = @()
    $details = @()
    foreach ($db in $databases) {
        try {
            $publicTables = Get-Cell $db "SELECT COUNT(*) FROM pg_catalog.pg_tables WHERE schemaname='public';"
            $size = Get-Cell $db "SELECT pg_size_pretty(pg_database_size(current_database()));"
            $ledgerPresent = (Get-Cell $db "SELECT to_regclass('public.ago_schema_migrations') IS NOT NULL;") -eq "t"
            $recorded = @{}
            if ($ledgerPresent) {
                $migrationRows = @(Invoke-ReadOnlySql $db "SELECT filename || '|' || sha256 FROM public.ago_schema_migrations ORDER BY filename;")
                foreach ($line in $migrationRows) {
                    $pair = $line -split '\|', 2
                    if ($pair.Count -eq 2) { $recorded[$pair[0]] = $pair[1].ToLowerInvariant() }
                }
            }
            $missing = @($expected.Keys | Where-Object { -not $recorded.ContainsKey($_) } | Sort-Object)
            $mismatch = @($recorded.Keys | Where-Object {
                $expected.ContainsKey($_) -and $expected[$_] -ne $recorded[$_]
            } | Sort-Object)
            $unexpected = @($recorded.Keys | Where-Object { -not $expected.ContainsKey($_) } | Sort-Object)
            $matched = $recorded.Count - $mismatch.Count - $unexpected.Count
            $tableCounts = [ordered]@{}
            foreach ($table in $tableNames) {
                $hasTable = (Get-Cell $db "SELECT to_regclass('public.$table') IS NOT NULL;") -eq "t"
                $tableCounts[$table] = if ($hasTable) {
                    Get-Cell $db "SELECT COUNT(*) FROM public.$table;"
                } else { "absent" }
            }
            $summaries += [pscustomobject]@{
                Database = $db; PublicTables = $publicTables; Size = $size
                Applied = $recorded.Count; HashMatched = $matched
                Missing = $missing.Count; HashMismatch = $mismatch.Count
                Unexpected = $unexpected.Count
                Current = ($missing.Count -eq 0 -and $mismatch.Count -eq 0 -and $unexpected.Count -eq 0)
            }
            $details += [pscustomobject]@{
                Database = $db; Tables = $tableCounts
                Missing = $missing; HashMismatch = $mismatch; Unexpected = $unexpected
                LatestRecorded = if ($recorded.Count) { @($recorded.Keys | Sort-Object)[-1] } else { "none" }
            }
        } catch {
            Write-Warning "Database $db could not be audited: $($_.Exception.Message)"
            $summaries += [pscustomobject]@{
                Database = $db; PublicTables = "?"; Size = "?"; Applied = "?"
                HashMatched = "?"; Missing = "?"; HashMismatch = "?"
                Unexpected = "?"; Current = "ERROR"
            }
        }
    }
    Write-Output ""
    Write-Output "AGO READ-ONLY DB COMPARISON | Expected SQL migration files: $($expected.Count)"
    $summaries | Format-Table -AutoSize | Out-String -Width 200 | Write-Output
    foreach ($item in $details) {
        Write-Output "Database: $($item.Database) | Latest tracked migration: $($item.LatestRecorded)"
        foreach ($entry in $item.Tables.GetEnumerator()) {
            Write-Output ("  {0,-25} {1}" -f $entry.Key, $entry.Value)
        }
        foreach ($name in @("Missing", "HashMismatch", "Unexpected")) {
            $list = @($item.$name)
            if ($list.Count -gt 0) {
                Write-Output ("  {0}: {1}" -f $name, ($list -join ", "))
            }
        }
        Write-Output ""
    }
    Write-Output "NOTE: A schema match alone does not prove data correctness, ownership or usable approvals."
    Write-Output "No database was changed. Do not migrate or initialize until the founder selects the intended source after reviewing this report."
} finally {
    if ($null -eq $oldPgPassword) { Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue }
    else { $env:PGPASSWORD = $oldPgPassword }
    if ($null -eq $oldPgOptions) { Remove-Item Env:PGOPTIONS -ErrorAction SilentlyContinue }
    else { $env:PGOPTIONS = $oldPgOptions }
    Remove-Variable securePassword -ErrorAction SilentlyContinue
}
