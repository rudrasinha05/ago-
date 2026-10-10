# AGO local operations (Windows PowerShell)

The existing application database and founder account remain in use. Run from `C:\Users\rudra\Projects\ago-\apps\backend` with your local connection already configured. Keep the running server in its own terminal.

## Start and inspect
```powershell
python -m ago.local_ops doctor
python -m ago.local_ops serve --port 8010
```
Open http://127.0.0.1:8010/console/. In another terminal (monitor needs no database password):
```powershell
cd C:\Users\rudra\Projects\ago-\apps\backend
python -m ago.local_ops monitor --port 8010
```
`alert: false` and exit 0 mean both health endpoints are healthy. `alert: true` means investigate the running-server terminal and doctor. Never kill an unidentified process to free a port; select another port instead. Restart invalidates the ephemeral browser session: log in again using the same organization/account.

## Back up before updates
Stop the server and other database writers. In the terminal with the database connection configured:
```powershell
$env:Path = "C:\Program Files\PostgreSQL\18\bin;" + $env:Path
$backupPath = Join-Path ([Environment]::GetFolderPath('MyDocuments')) ("ago-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.dump')
python -m ago.local_ops backup --output "$backupPath" --confirm
python -m ago.release_ops verify-backup --archive "$backupPath"
```
Keep both the `.dump` and `.dump.manifest.json`. A backup is not full recovery proof; test restoration separately. Include private object storage if configured. Do not put these files into Git.

## Isolated recovery drill
In pgAdmin create an **empty** database `ago_restore_drill`. It must be separate from `ago_test`. Configure the target without typing passwords into command history:
```powershell
$sourceUri = [uri]$env:AGO_POSTGRES_DSN
$targetUri = [System.UriBuilder]::new($sourceUri)
$targetUri.Path = '/ago_restore_drill'
$env:AGO_RESTORE_TEST_DSN = $targetUri.Uri.AbsoluteUri
Remove-Variable sourceUri, targetUri
python -m ago.local_ops restore-drill --archive "$backupPath" --confirm
```
Success reports `restored: true` and `schema_verified: true`. A populated target is refused. This does not change your active connection or delete your original database. For private objects, follow the matching storage recovery workflow before switching databases. Retain matching Git revision with each backup.
