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
4. Launch `./scripts/ago.ps1 serve`: the local PowerShell wrapper launches
   the market watcher with one-hour cadence when the tenant ID is configured.
   Or run `./scripts/ago.ps1 market-watch` in its own terminal.
5. Open Organization → Continuous Market & Opportunity Intelligence. Verify
   a real feed-health record, sourced URLs, observed scores, CEO nominations
   and the lack of falsely claimed marketing publication.
6. If the PC is off or no PostgreSQL service is available, the local observer
   **cannot keep running**. For true 24/7 operations deploy managed workers,
   durable queues, outbound quotas, backup/restore, incident alerts and monitoring
   only under an owner-reviewed deployment change.

Example (values are placeholders):
```powershell
$env:AGO_MARKET_TENANT_ID = "<actual-tenant-uuid-from-AGO-tenants>"
.\scripts\ago.ps1 serve
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
