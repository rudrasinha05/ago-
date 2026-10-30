# Durable notification read state — 30 October 2026

Continuation of the Founder-requested full-stack fixes on develop, starting at
0ea479b691f95dbc91421539cfa537b18a8d6de8. This closes the missing backend for the
existing notification center's Mark all read action (issue #4/#7). The user
requested frontend and backend completion; existing unrelated work is preserved.

## Behavior and exact contract

- Migration 066 adds a cursor keyed by tenant and authenticated human reader,
  with a composite user foreign key. It does not modify historic work events.
- GET /v1/organization/company/notifications keeps its existing event pagination
  and lifetime by_employee counters. Additive read_through_id, unread_count and
  unread_by_employee describe the entire currently visible unread ledger, even
  when only 100 events are returned or the forward page is empty.
- POST /v1/organization/company/notifications/read accepts only through_id, an
  integer from 0 through JavaScript's maximum safe integer. Tenant and reader
  come exclusively from the signed session. Existing organization:read and
  task:read permissions are required, plus a live active human identity.
- A nonzero watermark must identify an event visible under the same policy as
  GET. Unknown, future, foreign-tenant, unrelated-employee and ordinary chat
  message IDs cannot acknowledge notifications. Failed requests do not mutate.
- An atomic GREATEST upsert prevents retries/older tabs from decreasing state.
  Events after the selected watermark stay unread. State persists in PostgreSQL;
  no browser storage, global counter or approval authority is introduced.
- The existing frontend uses server-returned counts after acknowledgement. Its
  browser regression now remounts the organization workspace to verify the
  acknowledged state is retained rather than held only in component memory.

The existing founder vs employee event visibility policy is retained. This
change is a read acknowledgement, not project approval, QA or release evidence.
The cursor acknowledges events through a selected ID; it is not proof that the
human individually inspected every historical item or an exactly-once event bus.

## Verification

New signed PostgreSQL tests cover persistence through a fresh repository,
new events, empty forward pages, >100 events, independent users, tenant and
employee isolation, invalid IDs, inactive readers, authentication and strict
input validation. Existing browser tests cover the numeric badge and action.
Exact additive API, repository method and SQL-access contracts are registered;
no existing operation fingerprint or architectural module boundary was changed.

Local SDK: 43 passed. UI compatibility: 20 passed. Full local backend initial
run: 1043 passed, 252 skipped, one SQL-access contract failure; corrected by
registering only the new cursor table and rerunning the affected guard/tests.
PostgreSQL tests are not counted as passing on a host without PostgreSQL.
Final same-commit CI is the integration acceptance gate, reported with its SHA.

## Remaining scope

This notification flow does not complete the unified project → local Ollama →
Docker QA → independent human review → AGO GitHub delivery journey. Owner-host
Windows/Ollama/device acceptance and other original architecture backlog stay
separate. No production, paid model call, owner database migration or release
was performed. Existing installations require migration 066 via the established
operator migration process before running this new backend.
