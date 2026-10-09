# M1.4 Event Operations Integration

Delivered:
- CLI migration entrypoint: `python -m ago.event_runtime migrate --dsn <DSN>`
- Application-facing `serve_worker(dsn, configured_bus, worker_id=...)` coroutine.
- Worker translates event bus handler failures into outbox retries.
- Operational CLI deliberately refuses to start a worker without registered application handlers; otherwise events could be silently acknowledged.

**Important:** Starting a worker is an application lifecycle concern and is not wired into the API startup yet. Long-running handlers still need lease renewal and handler idempotency. The PostgreSQL test suite needs a live database and migrations. Do not run worker against production events until domain handlers, retries, idempotency and security review are complete.
