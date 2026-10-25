# AGO local serve: no-secret failure diagnosis

A local `serve` failure may mean the database connection variable has not
been set in the **same PowerShell session** as the Ollama flags.

From repo root:

```powershell
.\scripts\ago.ps1 doctor
```

Read `ready`, `database_configured`, `database_local`,
`migrations_applied`, `stage_safe` and `signing_secret`.

- `database_configured=false`: restore the **existing development DB** DSN in
  this shell as `$env:AGO_POSTGRES_DSN`, without showing it in chat or logs.
  Do not create or reset a new database.
- `database_local=false`: ensure the DSN targets localhost PostgreSQL, not
  a remote host.
- `migrations_applied=false`: this can mean no PostgreSQL connection,
  mismatched deployed migration checksums, or missing migrations. Confirm
  the existing local server is up and accessible before deciding if reviewed
  migrations are needed; do NOT run destructive migrations blindly.
- `signing_secret=too_short`: use an appropriate secret or let the development
  launcher generate an ephemeral one by not setting the variable.
- `stage_safe=false`: development/test only.

The PowerShell launcher now runs doctor **before** displaying any startup
success messaging. A failed Python serve prints the same safe diagnostic
booleans, never the raw DB exception, credential or DSN.

After `ready=true`, launch
`$env:AGO_LLM_MODEL="qwen2.5-coder:1.5b"; .\scripts\ago.ps1 serve`
with the other prior local AI flags in the same terminal. A genuine started
server prints Uvicorn startup and listens on 127.0.0.1:8000.

This is an operator UX fix only: does not prove seven-role execution, QA or
AGO P1 acceptance.
