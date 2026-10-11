# Sections 21–27 remaining gates — implementation contract

Owner instruction: complete the remaining work. Original blueprint Sections21,
24,26,27 and master checklist version11 were read on2026-10-11. This contract
extends missing functionality inside the existing personal-localhost modular
backend/PostgreSQL/console architecture. It does not authorize an unattended
policy deployment, new service, paid provider or a Windows database migration.

| Original open gate | Concrete work and acceptance |
|---|---|
|21 organization lifecycle|Persist and validate all eight operating phases, optimistic cursor, source-linked results, exact retry and atomic offline dispatch; opt-in signed localhost loop resumes after restart.|
|24 real expenses|Retain source document bytes/digest, period/category/currency/amount and independent verification of claims. No document or human review is provider authentication.|
|24 observed ROI/opportunity cost|Reconcile a chosen period's reviewed actual cost/revenue evidence; baseline and alternative assumptions stay explicit.|
|24 invoice/revenue reconciliation|Require independently reviewed exact source evidence and match invoice amounts to independently reviewed bank evidence; reject mismatched amounts/currencies/periods and duplicate invoice/payment reuse.|
|24 audited optimization|Store auditable reconciled metrics and advisory optimization preserving QA, permissions and budgets. Genuine financial acceptance awaits owner records.|
|26 measured quality|Record actual independent QA group metrics and version provenance; enforce Section14 architecture measurement rather than asserting causal prompt quality.|
|26 controlled experiments|Pre-register disjoint unfinished task cohorts with immutable seeded assignment, explicit variant definitions and hypothesis before execution, independently approve registration, measure later same-cohort QA, uncertainty and missing outcomes.|
|26 promotion/rollback audit|Observe and audit actual independently reviewed OOS capacity baseline/candidate/rollback applications, prove exact baseline restoration and application order. Evolution never applies a change; source/security policy deployment remains outside the frozen advisory architecture.|
|27 calibration|Freeze QA and cycle-time/deadline baselines before outcomes, report held-out errors, interval coverage, sample counts and unfinished/unknown outcomes. Broader economic/growth/market validation awaits true longitudinal data.|
|27 continuous sync|Opt-in signed localhost loop captures one-way immutable projections on each cycle with predecessor/source provenance, freshness and replay comparison; no simulated state writes.|

Negative acceptance: anonymous/cross-tenant access, self review, wrong approval,
stale cursor, replay dispatch, post-outcome experiment enrollment, substituted
variants/seed, reused invoice/payment, mixed currency, future observation leakage,
source truncation and authority escalation must fail closed or be explicit.

Verification: disposable actual PostgreSQL migrations, existing full tests,
targeted security/failure-path tests, canonical console workflow integration,
all unchanged architecture/API/coverage gates and final-head GitHub CI.

Original checkboxes close only where their original criterion is proved. Genuine
financial data, broad longitudinal outcome series and founder Windows acceptance
cannot be replaced by disposable tests.

## Implemented closing workflows

- Eight durable lifecycle checkpoints with exact retry, stale-cursor rejection,
  atomic offline dispatch and rollback on a crash. The signed localhost operator
  command `python -m ago.local_ops operate --iterations 1` resumes the saved phase
  and advances eight steps; polling is explicitly opt-in. Only separately approved
  offline tasks execute; independent QA remains required. Every learning phase
  stores measured diagnostics and a one-way Twin capture.
- Actual invoice/bank file or text bytes, immutable digest and claim attribution,
  readable source review/download, exact independent review and same-currency/
  amount/category/period reconciliation. Unique documents, content digests and
  claims cannot be charged twice. Manual review never asserts provider or bank
  connector authentication. Baseline and opportunity-cost assumptions stay explicit.
- Prospective, reproducible balanced assignment of unfinished same-employee
  offline tasks to two fixed packet layouts. Registration must be independently
  reviewed before dispatch. Actual handler results retain variant/registration
  digest, and later independent QA produces sample counts, pass rates, Wilson
  intervals and pending observations. This measures a narrow layout intervention,
  not arbitrary prompts, models or architecture superiority.
- Diagnostics retain real output QA ratios by employee/department/workflow/action,
  exact handler version digest and actual Section14 contract results/policy digest.
  Evolution can audit three already applied, independently approved capacity
  configurations and verify that the rollback restored the original scope/value
  in application order. It never changes source, deployment, authority or policy.
- Periodic Twin capture links predecessor/source digests, timestamps, individual
  source records, freshness and explicit truncation/cap warnings. Repeated captures
  preserve prior versions. High-frequency observations do not crowd pending reviews
  out of the default dashboard. Exact kind queries retain full bounded history.
- Frozen QA plus empirical elapsed-time/deadline baselines are compared with later
  same-cohort independent QA. MAE, empirical range coverage, deadline error, unknown
  training, unfinished samples and missing economic dimensions remain explicit.
  Already observed tasks cannot be enrolled retroactively through an old snapshot;
  exact retries return the original frozen forecast.

## Verification checkpoint and final-head rule

The first implementation checkpoint is `44b34879dfa7ce0d7cbb843236a99b461dc59e7a`.
All nine actual jobs succeeded: main [38115503046](https://github.com/rudrasinha05/ago-/actions/runs/38115503046)
and independent backend [38115503005](https://github.com/rudrasinha05/ago-/actions/runs/38115503005).
571 backend tests passed on each Python3.11,3.12,3.14 with actual PostgreSQL,
no database skips; coverage87.55% on3.11 and87.53% on3.14. Builds, migrations038,
Docker, backup/restore, real storage recovery and browser/accessibility jobs passed.
The closing refinements additionally verify crash rollback, same-key frozen-forecast
retry, explicit source caps, pending-review retention and readable file review.
Their exact closing SHA/green CI evidence is recorded in the single master checklist
**after** the closing commit's own jobs succeed; this checkpoint alone does not
accept later changes. API additions are frozen in the existing fingerprint manifest;
old endpoint/schema fingerprints are retained except the additive evidence-kind filter.

## Original acceptance still dependent on real evidence

The local mechanics cover five previously open narrow engineering checks:
organization lifecycle, measured quality, controlled comparisons, real approval/
rollback auditing and one-way periodic synchronization. Four Section24 gates still
need genuine owner financial sources and observed business value. Section27 broad
calibration still needs prior predictions and later true deadline/cost/revenue/growth/
market outcomes over time. Tests prove software behavior, not these real outcomes.
No owner Windows pull, verified backup, additive migration038 or local acceptance
has occurred. No new cloud/provider account, payment or production deployment is
required by the personal-use implementation.

## Consolidated local rollout and rollback

After closing CI is green, make one existing `develop` pull, retain the normal
verified backup/doctor workflow and explicitly apply additive migration038 using
`python -m ago.event_runtime migrate`. Stop the old worker/server before upgrade.
Never reset the database or recreate the organization. Run doctor, restart localhost
and inspect Organization workflows; use the distinct reviewer for documents,
registrations and control changes. `operate` asks for signed-session credentials
in memory and stops on expired authentication or permission/dispatch failure.
Without the opt-in loop, capture is manual and staleness is visible.

Rollback stops the new worker/server first.038 is additive; do not drop immutable
source/assignment/reconciliation history. Older code cannot dispatch enrolled
experiment tasks safely, so do not downgrade while enrolled work remains active.
Use the existing isolated restore-drill procedure with a verified pre-upgrade
backup if recovery is necessary; never overwrite the founder's live database.
