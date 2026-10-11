# Section29 — Corporate Constitution for personal localhost

Owner request 2026-10-11: finish actual vision-critical implementation, preserve architecture,
and deliver one consolidated pull. Original blueprint Section29.1–29.13 (Library original
lines4431–4715) and master checklist version13 were read. No new service, provider,
public deployment or separate database is introduced.

## Frozen acceptance

1. Immutable highest laws above DNA, strategy, OOS, economy, tools, knowledge and simulation.
2. Authenticated persisted human-founder authority; AI identities cannot amend or declare emergencies.
3. Separate exact review of legal/security/architecture/audit/executive domains, independent of author.
4. Complete amendment classification, affected rights, risks, alternatives, dissent, rollback,
   monitoring and propagation package, bound to actual immutable tenant Twin simulation.
5. Exact immutable digest, stale-version rejection, monotone adoption history, effective dates,
   idempotent identical retries and changed-retry rejection. Recovery uses a new reviewed version.
6. Shared authenticated mutation guard and permission/execution guard; role grants, DNA,
   ordinary approvals, Meta Brain, marketplace and the opt-in HTTP local worker cannot bypass it.
7. Narrow temporary emergency restrictions, maximum24h; audit, identity recovery, human decisions
   and reads continue. Expiry removes temporary restrictions but retains mandatory postmortem.
   Another emergency cannot silently chain without independent prior incident closure.
8. Independently reviewed exact postmortem/recovery evidence before early closure; immutable history.
9. Canonical Next.js/compatibility Governance UI displays laws, current version, amendment packages,
   incidents, evidence and review/activation/recovery. Independent approval dialog loads exact source.
10. PostgreSQL, cross-tenant, revoked human, AI authority, unknown/duplicate contexts, immutable-row,
    request/execution-denial audit, actual browser and existing full regression acceptance.

## Implementation

Migration040 adds five immutable governance tables and database review/adoption/closure guards.
Existing ApprovalRepository owns all writes. SecurityControls owns the shared read-only policy
check and append-only denied-operation audit. Every authenticated business mutation is classified
at the common request dependency; actual executor permissions also consult policy. The existing
local worker calls these authenticated endpoints and stops on containment denial.

The baseline contains twelve fixed constitutional laws. A proposal can restrict operational
contexts; it cannot rewrite those laws, grant authority, weaken approval/QA/security or disable
audit. Restoration of a previous operational policy requires a fresh independently reviewed
version. Read-only baseline version0 is always present even before an owner adopts version1.

Amendment requests create five exact-digest review requests. At minimum the founder and another
active human participate; the same independently authorized human may review multiple domains.
This local board does not assert that reviewer is external counsel, auditor or security assessor.
Human leadership remains responsible for legal judgments. A short elapsed requested effective
minute is clamped to the actual adoption instant, so changes never take effect retrospectively;
future versions become authoritative at their recorded time. Only one scheduled head can precede
another adoption. No code, grants, DNA or historical workflow records are silently rewritten:
central enforcement propagates authority immediately, and other changes retain their own approvals.

Emergency containment blocks starting subsequent business operations in selected contexts;
it does not interrupt an already running external request or roll back previously committed work.
Identity/security repair and audit/read access stay available to humans. Immutable incident and
postmortem evidence survive expiry/closure. No emergency expands AI authority or permanently amends law.

Trusted database administrators and source-code operators can change the deployment itself;
this implementation protects registered runtime/API/executor paths, not hostile root ownership.
Static protected-writer and dependency rules preserve the governance boundary. Existing external
production security assessment and legal certification remain outside personal-localhost scope.

## Architecture and compatibility

No module added. Four approved inward dependencies: transport api_m2 → governance_domain;
governance persistence → security Principal; security_controls and employee state in enterprise_store → governance_domain constants.
All remain within existing allowed layers/contexts.109 modules/307 recorded imports, zero violations.
Five new governance SQL owners are restricted to governance. Typed ports, exact constructor contracts,
source inventory and additive API snapshots are updated; existing route/schema fingerprints unchanged.
Six additive endpoints are under /v1/governance/constitution. Existing approvals still decide reviews.

## Personal use

Governance displays the immutable laws immediately. For an amendment, capture executive evidence,
run an actual Twin scenario, propose a version with complete context and obtain five domain reviews
from an independent human. The founder adopts the reviewed exact version. For immediate containment,
choose Emergency stop and its context/expiry. Prepare and independently review actual recovery evidence,
then close the incident. During containment the owner can still inspect records and make human reviews.

One consolidated owner update: stop old worker/server, verify backup using currently installed code,
fast-forward develop, install the existing dependencies/build and package Next.js if using canonical
workspace, explicitly apply migrations through040, run local doctor and start loopback server.
No database reset, destructive cleanup, new tenant or production rollout. The owner's Windows machine
has not been operated in this chat. Its local acceptance remains separately observable.

## Acceptance evidence

Recorded after the exact published head CI is verified in the single master checklist.
Local validation does not claim PostgreSQL cases passed without a migrated database.
Tests include authentic disposable PostgreSQL runtime/HTTP approval and containment behavior,
immutable direct-DML guards, AI/foreign/revoked identities, expiry history, XSS-safe templates,
and the shipped Next.js two-human emergency/recovery journey. This journey also found and
fixed the existing Next.js dialog Cancel/close-button bridge after a denied action; navigation
and independent recovery now remain available. CI fixtures are software evidence.
