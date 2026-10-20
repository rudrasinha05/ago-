# Company autonomy — evidence-backed first gate

AGO uses the single configured `AGO_POSTGRES_DSN` for tenant-scoped company
records. Distinct Next.js workspaces and their navigation do not imply
separate databases. A standard PostgreSQL installation also exposes the
maintenance database `postgres`; the populated user database is `ago_test`.

## Gap and opportunity radar milestone
Migration 054 adds tenant-isolated, time-bounded catalog opportunity hypotheses.
A trusted `CompanyChat.scan_opportunities` creates at most three per tenant
per calendar month, only when no actual task is currently *running*.
The per-tenant row lock and unique key make retries and concurrent watchers
idempotent. Every idea has a recorded real executive owner (or explicit
founder escalation) and exact founder-only `ago_approval_requests` entry
with an audit row. No AI employee is impersonated as having personally
researched or proposed the idea: the displayed discovery type is
`catalog_hypothesis`. These examples do NOT represent actual demand,
customer interviews, sales, or validated monetization.

An approved opportunity is approval **to begin research/planning**, not an
automatic project, contract, payment or completed delivery. Executable
delegation, market validation, customer discovery, compliant outreach,
real payment evidence, billing, measured ROI, SLA/incident recovery and
always-on infrastructure still require separate verified integrations.
The scanner never touches external services.

## Local observer
From `apps/backend`, with your current local DSN and applied migration:
`python ../../scripts/opportunity_scan.py --tenant-id YOUR_ACTUAL_TENANT --once`
or omit `--once` to check hourly. This is NOT an always-on cloud service;
it stops when the process or machine is stopped. Only the selected tenant
is touched. Never configure it against the production database without
deployment review.

## Governance
Founder has the sole operational Approve/Deny authority. A board title or
CEO role does not grant it. CEO/COO/CTO can be the delivery-accountable
manager, not a fictional person who completed the research. Outbound mail,
ads, buying services, collecting money and legally binding contracts have
separate authorization, budgets, consent and evidence requirements.
