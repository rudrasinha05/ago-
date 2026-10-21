# AGO — Continuous Opportunity & Company Growth (local milestone)

## Business rule
Company research must operate **even while governed delivery tasks are running**.
Research, project governance and earning revenue are separate workflows. No claim
of 24/7 cloud uptime, AI CEO live cognition, actual sales or posted promotions
is made without deployment and external evidence.

## Actual modules on develop
- `deploy/sql/055_continuous_market_intelligence.sql`: tenant-scoped external
  signal/source ledger, source-health history, founder-approved nomination
  linkage, draft social campaigns. Uses **the existing one PostgreSQL DSN**.
- `scripts/company_market_watch.py`: fixed-source allowlisted HTTPS RSS fetcher
  with bounded response size, XML/URL checks, deduplication, descriptive scoring,
  automatic recovery after transient failures, three nomination slots/week and
  strictly draft-only social copy. It runs independently of active delivery tasks.
- `GET /v1/organization/company/market-intelligence`: signed-session,
  tenant- and RBAC-scoped evidence, recommendations and marketing drafts.
- `GET /v1/organization/company/projects?limit=50&offset=N`: pageable company
  project catalog; `GET /v1/organization/company/projects/{id}` shows actual
  plan, brief, accountable manager, suggested/actual assignees, task status and
  recorded independent QA. The UI lists all pages on demand, rather than hiding
  everything after five projects.
- Company cockpit links directly to researched opportunities, full project
  portfolio, workforce, brain, approval requests and internal conversations.

## Source trust and CEO responsibility
The source set intentionally starts small, from fixed feed endpoints:

1. arXiv Computer Science AI RSS — published preprints, **not peer-reviewed
   or validated commercial demand**.
2. NIST official news and cybersecurity RSS — government-source developments.
3. NIST Manufacturing Innovation blog RSS — articles and industrial context.
4. OpenAlex works metadata API — CC0 research metadata (not full texts).
5. Crossref works REST API — open bibliographic metadata (no abstracts or full texts).

Publisher feeds that restrict commercial use, including The Guardian RSS,
are **not** enabled by default. Hacker News has commercial-use conditions and
is likewise excluded pending applicable authorization. Feed content is never
resold, mirrored or used to train a model.

Only title, summary, time and source link are ingested; linked sites are **not**
crawled and remote text is never executed as an instruction. Network redirects
and nonallowlisted feed URLs are rejected. The signal rank is a transparent
keyword heuristic, NOT proven willingness to pay. Every source is individually
recorded; failure does not manufacture a signal.

When a real AI CEO employee is already configured and a real active human founder
exists, the *trusted deterministic CEO-support policy* may nominate at most
three high-relevance market signals per calendar week. The CEO is the recorded
accountable owner; **this is not evidence the AI CEO independently researched
or chose a business**. Nominations create immutable, scoped founder requests:
approval permits customer validation and governed planning only. Every project
must still satisfy strategy, delivery, QA and release gates.

No CEO exists? Sources are still preserved; nominations pause instead of
inventing an executive. Creating departments or employees requires a separate
reviewed delegated-organization charter; do not bypass existing HR guards.

## Windows localhost operator instructions
1. Back up the live AGO database before migrating. Ensure the source code
   branch, backup manifest and migration plan match.
2. From repository root, run the existing reviewed local migration process
   (`./scripts/ago.ps1 migrate`) and explicitly type `MIGRATE` after verifying
   `AGO_POSTGRES_DSN` points to the intended **localhost** database.
3. Obtain the tenant UUID from the existing operator `tenants` command.
   Set `AGO_MARKET_TENANT_ID` to **that actual UUID**, not a random one.
4. **Founder-controlled startup:** run `./scripts/ago.ps1 serve` to start only
   the localhost server. Setting `AGO_MARKET_TENANT_ID` does NOT start any
   watcher. If and only if the founder chooses to perform research, open a
   **separate terminal** and run `./scripts/ago.ps1 market-watch`. Stop either
   foreground process with Ctrl+C; closing the terminals stops the work.
5. Open Organization → Continuous Market & Opportunity Intelligence. Verify
   a real feed-health record, sourced URLs, observed scores, CEO nominations
   and the lack of falsely claimed marketing publication.
6. **The founder decides when the laptop is on, off, awake or asleep.** AGO
   must never wake the PC, install OS startup tasks, run hidden scheduled jobs,
   request hosted infrastructure, or enable cloud service on its own. If the
   laptop is off or PostgreSQL is unavailable, the local observer stops and
   resumes only when the founder manually starts it again.

Example (values are placeholders):
```powershell
$env:AGO_MARKET_TENANT_ID = "<actual-tenant-uuid-from-AGO-tenants>"
.\scripts\ago.ps1 serve
# In a SEPARATE terminal, only when the founder explicitly wants research:
.\scripts\ago.ps1 market-watch
```

## Promotion / outreach / money — gates still open
- Marketing drafts for approved *active* projects are generated with truthful
  under-development language and linked to projects; source feed text is not
  pasted into outgoing ads.
- **No actual** LinkedIn, Meta, Instagram, X posting, ad spending or cold email
  is implemented or claimed by this watcher. Connect official authorized
  business APIs/accounts, verify platform TOS, per-account posting limits,
  opt-in/anti-spam controls and an approved content policy. Record an external
  permalink and source evidence before changing publication status.
- No verified revenue or payout is entered without payment-processor/bank
  settlement evidence and reconciliation. Cash received != profit: costs,
  taxes, refunds, chargebacks and customer support must be accounted for.

## Self-modification constitution
AGO must not edit its own release gates or founder authority without an
independent review. Allowed future path: propose a patch on `develop`, run
sandbox tests and security lint, obtain code review and human authorization
for governance changes, verify CI on exact SHA, and retain a rollback commit.
An AI patch proposal is not an approved or self-deployed upgrade.

## Acceptance evidence
Only mark the implementation verified after: all Section 3/5/13 contracts
green, migration 055 applied against a disposable test DB, parser/tenant
isolation tests, browser accessibility and signed-session smoke, all final
SHA full CI jobs green, and a local live feed run. GitHub commits alone do not
prove production or customer revenue.


## Latest bounded yellow-status engineering improvements
- `deploy/sql/056_approved_market_project_lineage.sql` creates an immutable
  source-signal → project join guarded **inside PostgreSQL**. The source must
  be shortlisted and approved by the same active human founder. The requester
  must be its real recorded executive owner. A forged URL or merely high score
  cannot create a project.
- After approving a CEO-nominated research signal, the founder may select
  **Create governed project draft** in the market intelligence view. This
  calls `POST /v1/organization/company/market-intelligence/{id}/project`,
  creates one idempotent five-stage *draft* and links the original source.
  It does not assign executable work or enable outreach, payments, ads or a
  release. Department creation and autonomous CEO execution require their
  own governed delegation policy.
- The project inspector shows the actual governed task, AI run status,
  independent QA verdict, QA evidence, real-stage QA completion ratio and
  evidence-backed project health. **Export evidence report (.md)** generates
  a client-side Markdown snapshot of this authorized data; no fake code
  diffs, external GitHub PR or publication are asserted.
- The Management Workload desk measures completed, failed and unreviewed
  tasks, actual independent QA and workload-weighted suggestions for
  existing employees matching open stages. It never hires, grants access,
  changes assignments or fabricates employee performance.
- `scripts/company_readiness_audit.py` (PowerShell action `company-pulse`)
  checks migration integrity, researcher scan recency, failed tasks,
  unreviewed completions, stalled in-flight tasks and stale agent runs.
  It prints **only nonsecret structured observations** and operator actions.
  No destructive restart or repeat of non-idempotent external effects.
- `scripts/ago.ps1 serve` starts the local server **only**. The previous
  automatic watcher process has been removed; the founder explicitly launches
  `scripts/ago.ps1 market-watch` when desired and terminates it with Ctrl+C.
  No cloud service or laptop power-management changes are part of AGO.

### Quick local health check
After backing up the correct database, applying reviewed migrations 055-056,
verifying the authenticated founder tenant and starting AGO:

```powershell
$env:AGO_MARKET_TENANT_ID = "<actual existing tenant UUID>"
.\scripts\ago.ps1 company-pulse
```

The pulse's `observed_ok` means its limited health conditions were observed;
it does **not** mean accepted marketing/publishing/revenue or production security.
Fresh source checks can individually report degraded even when worker is alive.

### Acceptance still required
- Restore exact final-SHA architecture CI and the independent-review/founder
  approval regression matrix; never downgrade a 403 just to pass old tests.
- Verify test database migrations 055-056, signed-session UI navigation,
  one CEO-sourced approval → one draft lineage, no side effects, test backup
  and actual local server run. Release is not certified by repo commits.


## Explicit opt-in Docker preview research worker (host must already exist)

An isolated market research sidecar is packaged in the non-root Docker image
and declared in `deploy/docker/compose.market.preview.yml`. It has a bounded
hourly poll interval, read-only root, no public port, only database/internal
network plus separate research egress, no Docker socket, and Docker
`restart: "no"` (founder manual start). **This is NOT 24/7 cloud hosting**, production
secrets management or an approval to expose the service publicly.

Do not run this with a production database. All preview data is test/demo
data; never use it for customer sales, spend or production assertions.

From the repository root, after configuring throwaway preview secrets and
obtaining a real existing preview tenant UUID:

```bash
export AGO_PREVIEW_DB_PASSWORD="(a strong unique local preview secret)"
export AGO_PREVIEW_SESSION_SECRET="(a different random 32+ byte signing secret)"
export AGO_MARKET_TENANT_ID="(existing preview tenant UUID)"
docker compose -f deploy/docker/compose.preview.yml \
  -f deploy/docker/compose.market.preview.yml config --quiet
docker compose -f deploy/docker/compose.preview.yml \
  -f deploy/docker/compose.market.preview.yml up --build -d
docker compose -f deploy/docker/compose.preview.yml \
  -f deploy/docker/compose.market.preview.yml logs --tail=40 market-worker
```

The preview PostgreSQL must have migration 055–057 applied first using
the reviewed operator migration procedure; compose intentionally does **not**
silently migrate existing data. Worker allows only exactly
`postgresql://ago_preview:...@postgres:5432/ago_preview` in a deliberately
set `AGO_MARKET_PREVIEW_CONTAINER=true` process and only
`AGO_ENVIRONMENT=development`. The production path remains fail-closed.
Managed hosting and cloud databases are outside the authorized AGO scope.
The optional Docker Compose profile is for **local machine preview only**, and
must not be started without a founder action. Both the local API and database
containers and the optional worker have `restart: "no"`: they do not restart
without a founder-initiated `docker compose up` action. Laptop shutdown always
stops local work.

## Optional AI planning (not autonomous execution)

`project:plan` is now an opt-in bounded text-generation handler for
**already-approved** project-linked tasks with a stored founder intake.
Model calls require explicit `AGO_ENABLE_PAID_MODELS=true`,
`AGO_LLM_API_KEY`, `AGO_LLM_MODEL` and virtual-credit charge. Its output
is an advisory five-stage planning candidate requiring independent human QA.
It cannot create departments, hire, modify GitHub, execute code, override
approvals or claim product release. The default config makes no provider call.
