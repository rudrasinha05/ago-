# Organizational Calendar — Section30 source reconciliation

Original blueprint30.1–30.10 describes enterprise temporal governance. This implementation
uses the existing operations repository, task admission, queue, planning and one-way Twin;
it adds no service, database, scheduler daemon, external calendar or approval authority.

## Policy and ownership

Reviewed company, department and employee policies combine as constraints. They define
IANA zones, weekdays, working hours, dated regional holidays, overnight quiet hours,
human-supervisor and emergency-review coverage, support hours and AI continuous/rest limits.
`tzdata` supplies IANA data on Windows. DST gaps are rejected; an ambiguous occurrence
requires an explicit valid UTC offset. Recurrences preserve local wall time; monthly
recurrence clamps each occurrence to its month's end from the original day, including leap years.

Temporal owners and domains are explicit in `CALENDAR_DOMAINS`: operations owns business,
working hours, holidays, sprint, week, month, quarter, year, handoff and milestones;
economics owns budget cycles; human leadership owns hiring, promotion, performance and
constitutional reviews; architecture owns maintenance, release and freeze; security/operations
owns incident windows; Meta/departments own simulation and learning; human reviewers own
approval availability. Ownership is descriptive and does not grant privileges.

Annual/quarter/month/sprint/week/day/hour/task horizons are represented by nested cycle
windows, exact event times and reviewed goal/task links. Parent containment and dependency
handoff ordering are checked. Support/emergency coverage is reported as available,
unavailable or unconfigured; it never overrides a blocked execution window.

## Exact review and execution

Five package types are supported: policy, window, window cancellation, event links and
coordinated reschedule. An active persisted human founder authors a package against the
current organization revision. It freezes normalized specification, original input, source
state, rationale, dependency/deadline impact and digest. A different active authorized human
reviews the exact digest in Governance. Applying rechecks reviewer authority, source events,
source revision and current availability/conflicts. Changed retries, stale packages, private
source events, foreign references and AI authors fail closed. Independent QA remains separate.
Migration041 stores append-only proposals, applications and timing observations; PostgreSQL
triggers require a matching independently approved review and sequential revision.

TaskStore is the common guard for AI, trusted tools, GovernedExecutor and direct starts.
The actual database clock is checked immediately before claiming, under the tenant lock
shared with calendar changes. Ordinary API task starts also perform the check before the
business transaction so their denied timing audit survives a failed start. Task lifecycle
records actual start/completion/failure, not predicted completion. Internal callers that wrap
all work in a transaction retain that transaction's rollback semantics for denial audit.

Working time, holiday, quiet, supervisor availability, rest/continuous limits, current worker
and organizational mode, termination, maintenance, incident and release-freeze constraints
are rechecked. Reviewed execution and fiscal-budget windows constrain reservation bounds;
linked task events constrain starts and deadlines. Calendar availability never replaces
original task approval, predecessor QA, Constitution, capacity or trusted-handler checks.

The OOS queue skips unavailable candidates before leasing and prefers imminent public or
reviewed linked deadlines within its existing bounded100-candidate fair-priority selection.
Long-running workflows recheck at each governed task/lease transition. This is admission and
checkpoint governance: existing running handlers are not forcibly interrupted mid-call.

## Coordination, projection and limits

Ordinary private/tenant events and RSVPs remain available. Scheduling rejects a participant
conflict with a generic message and does not disclose the other event. Independently reviewed
shared-event rescheduling preserves original rows, cancels them atomically and creates exact
reviewed replacement IDs plus fresh invitations. It cascades through up to100 explicitly
linked downstream events; task/goal intent is not silently rewritten. Governed dependency
events cannot be cancelled through the ordinary creator-only cancellation shortcut.

Eligibility is read-only, uses one-minute resolution plus exact window boundaries, searches
up to14 days and distinguishes found/not-found/truncated. Query-local source caches avoid
re-reading persistent state for each prospective minute. It is a planning reservation, not
retrospective execution or an approval. Default unconfigured availability is explicitly UTC
continuous availability; it is not certified human coverage.

Due-cycle observation emits durable, idempotent opening/closing signals and human follow-up
ownership. Operating cycles record them; the explicit UI action can also observe them.
Planning feedback and immutable Twin snapshots include reviewed temporal policies, windows
and public links. Private events never enter this shared projection. Calendar controls expose
policies, cycles, exact packages, dependencies, reschedule impacts, availability and signals
in both Next.js and generated compatibility views. No external invitation/report is sent,
and a budget/HR/release/learning/simulation signal does not execute a business action.

Bounded projections:10000 reviewed changes (fail closed beyond this),100 recent proposals,
100 recent timing signals,100 reschedule events,52 recurrence slots within3 years,14-day
availability search. Existing task/queue/plan visibility and truncation remain explicit.
Original30.1–30.10 map respectively to scope, integrations, domain catalog, parent horizons,
availability policies, handoffs/rescheduling, shared admission, eligibility/constraints,
durable governance signals and ownership map.

## Verification commands

```bash
python -m ago.event_runtime migrate
python -m pytest -q tests/test_section30_calendar.py
python -m pytest -q tests_next/test_next_browser.py
python -m ago.architecture_guard check --json
```

Use only a migrated disposable PostgreSQL for tests. Original owner database must never be
used as a test fixture. Full final CI evidence is in `SECTIONS28_30_FINAL_ACCEPTANCE.md`.
