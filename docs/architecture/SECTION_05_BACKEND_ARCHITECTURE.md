# Section 5 — Backend Architecture (FastAPI)

Scope is the seven supplied Section 5 checklist requirements, on Section 4's
accepted modular monolith. The complete original blueprint is unavailable;
this is bounded source-backed acceptance, not a claim of exact source parity.

## Layers and executable boundaries

| Concern | Source ownership | Enforcement |
|---|---|---|
| Composition | `main`, operator entrypoints, trusted repository bindings | Build application, connect/close request database, configure adapters |
| Presentation | `api_*`, `console_api`, `auth_api`, `api_contracts`, `http_errors` | Typed input, signed principal, persistent permission checks, ports; no raw SQL execution or concrete store construction |
| Application | Plan/agent/tool execution, DNA evidence orchestration, session/console services | Transaction lifetime and context coordination; no raw database execution; resolve context-owned repositories |
| Domain | Approval/task/organization/memory values, `governance_domain`, `credit_domain`, `dna_domain` | Pure invariants and values, no database execution or HTTP authority |
| Infrastructure | Stores and nine context-specific `*_queries` repositories | Bound SQL parameters, row locks, persisted audit/state, caller-owned transaction connection |
| Shared foundation | `backend_contracts`, platform DI/settings/events | Framework-free database/cursor protocols and request-local constructor scope |

The registered root-module layout is intentionally preserved. Stores such as
`governance` re-export pure values for compatibility, while their SQL implementation
is registered as persistence. With the Section 7 storage extension, the source
inventory covers all 98 modules and 260 internal dependency edges. Section 14 forbids cycles and protects approval,
approval-audit and QA writes. Section 3 independently checks complete module/context
ownership and reviewed SQL table access. No schema or migration changed.

All raw application-service SQL moved to nine owned query repositories:
agent runtime, department automation, executive intelligence, Meta Brain,
plan execution, scorecard, tool catalog, enrollment and runtime. Query methods
have descriptive verb/table names and versioned signatures. The two dynamic
query selectors accept only the original frozen table roster or optional
snapshot filter; arbitrary selectors fail before database execution. Static SQL
string scanning is a drift gate, not a universal SQL parser; runtime parameter
binding, authorization and integration tests remain necessary.

Console profile/review/QA queries are owned by `ConsoleStore`; active-account
lookup belongs to `IdentityRepository`. `ConsoleService` retains one transaction
for task row locking, approval proposal and task attachment. `SessionService`
preserves committed failed-login throttle evidence. Independent human review,
tenant predicates and single-use governed task execution remain mandatory.

## Dependency injection and repository contracts

`backend_contracts.DatabaseConnection` and `Cursor` define the caller-owned DB
port. `repository_ports` defines 39 structural component protocols and trusted
default constructor bindings. `section05_backend_contracts.json` records every
public method signature for every connection-backed component. The guard compares
source methods, port signatures, constructor types and binding rosters; drift
requires a reviewed contract update.

FastAPI's cached `repository_scope` dependency receives the same `db_connection`
used for authentication and the route. Scope state is per request, never global;
connections are opened/closed by the dependency, not by the scope. A protocol and
its implementation resolve to one cached instance. Parameterized handlers are
constructed with their own options instead of reusing different handler settings.
Services pass the same scope into nested repositories, so trusted substitutes
cascade. Overrides live in application composition state and cannot be supplied
by API input. Permissions are still checked before invoking mutation ports.

Pure components continue explicit value/function injection. Background workers
retain `LeasedStore` injection and own a PostgreSQL event adapter per worker;
SQLite's event adapter remains a local test facility. They do not reuse an HTTP
connection or a global request cache. Existing platform singleton/scoped/transient
DI continues independently for settings/logging/event infrastructure.

Open evidence/payload parameters retain explicitly marked `Any` in legacy
repository ports; this is not a full static type-checking claim. HTTP DTOs and
domain validators constrain those values. A future remote service must serialize
published context values, not expose SQL cursors or connection objects.

## Typed inputs and business errors

All request DTO roots inherit `StrictInput` (`extra='forbid'`), including the
opt-in authentication router. Input booleans use `StrictBool`; employee kind,
memory visibility and terminal goal status are finite literals. UUID parsing,
length/range constraints and domain checks remain. Password whitespace is exact.
Clients previously sending ignored fields or string booleans now receive 422.
Authority continues to come from signed, active, nonrevoked sessions, not body
`authorized`, `tenant_id`, `actor_id` or reviewer fields.

Business HTTP errors retain `detail`, status and authentication headers and add:

```json
{"detail":"Permission denied","error":{"code":"permission_denied","request_id":"bounded-correlation-id"}}
```

Permission/not-found/invalid-request exceptions map to 403/404/400; PostgreSQL
integrity conflicts remain 409, rejected inputs 422, unknown failures 500, handler
failures 502 and unavailable dependencies 503. Unhandled exceptions use generic
messages. Validation strips submitted `input`, exception `ctx` and user-dependent
messages, so credentials and malformed bodies are never echoed. Bounded ASCII
correlation IDs appear in body and `x-request-id`; bearer challenges are preserved.
Readiness diagnostics and outer infrastructure/host/body perimeter responses keep
their own contracts; they are not business exception payloads.

## Future context contracts and validation

The nine Section 3 contracts define context ownership, published languages,
invariants, transactional consistency and durable-event/replay rules. Section 5
adds typed local ports, strict `/v1` input/OpenAPI contracts and uniform business
error metadata. Extraction requires versioned tenant/principal/auth/idempotence,
approval/QA and recovery envelopes, source-reviewed ownership and a gateway
adapter. This change creates no independent service, network client or database.

Run `python scripts/check_backend_architecture.py`, the Section 1/2/3/4/14 guards,
Ruff and the full PostgreSQL integration matrix. New tests cover port substitution,
request isolation, nested injection, unchanged permission gates, authority-field
rejection, strict values, secret-free failures, bearer challenges, closed query
selectors and malicious source/interface changes. CI also verifies the current
console, real Chromium, Docker, recovery and Next.js shells. See the acceptance
report for actual commit/run evidence. Rollback reverts this section as a unit;
there are no database down-migrations.
