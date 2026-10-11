# Sections 24, 26, 27 — six remaining measurement gates

Owner instruction, 2026-10-11: implement the six listed requirements in one batch.
Original blueprint Sections24.1–24.10,26.1–26.8,27.1–27.10 and master checklist
version12 were read before implementation. Existing FastAPI/PostgreSQL/canonical
console, signed RBAC, independent exact-digest review and immutable history remain
the approved architecture. No new provider, deployment, payment or model account.

## Frozen batch contract

| Gate | Executable acceptance |
|---|---|
|Actual expenses|Build a bounded, reviewed economic period from reconciled original cost/revenue sources; report model/storage/tool/execution/time totals, missing categories and exact provenance. Never invent missing costs.|
|Observed ROI/opportunity cost|Compare distinct reviewed baseline/candidate/optional alternative periods using observed net value, normalized daily amounts, cost per actual independently QA-approved deliverable and explicit comparability assumptions.|
|Invoice/revenue/budget reconciliation|Reuse exact source-byte independent review and duplicate-proof invoice/bank matching; add approved company budget attribution, variance and missing-budget warnings to the measured period.|
|Audited optimization|Freeze and independently review an intervention before the candidate period; measure later reviewed economics/QA against the frozen baseline, enforce quality and budget safeguards, retain change and rollback references. All recommendations remain advisory.|
|Broader quality|Version exact prompt/architecture/workflow/department/employee artifacts; independently review them; freeze a bounded weighted rubric and baseline/candidate study before samples; record exact source/output bytes and scores; independently review every sample; report scores, uncertainty, missing samples and dimension coverage. Human rubric measurement does not certify arbitrary design superiority or model execution.|
|Longitudinal Twin calibration|Freeze named dimension/unit/entity predictions and uncertainty intervals before the target period; reference already reviewed historical outcomes; accept later independently reviewed exact-period observations (financial values derived from reviewed economic periods); aggregate errors, bias, RMSE, empirical interval coverage, missing/overdue outcomes and provenance across multiple periods. No retrospective forecast or automatic operational write.|

Negative acceptance: cross-tenant/anonymous access, self review, unreviewed sources,
duplicate/reused cost claims, changed retry input, mixed currencies/units, overlapping
economic periods, budget substitution, retrospective study/forecast enrollment,
nonfinite metrics, out-of-range rubric scores, duplicate samples/outcomes, unknown
or future actual data, silent truncated histories and authority mutation fail closed.

Verification requires actual disposable PostgreSQL migration039 fresh/idempotent,
targeted domain/API/governance cases, canonical UI/browser integration, existing
full backend and unchanged compatibility/coverage/architecture checks, and the
exact published head's successful CI. The single master checklist is updated only
after evidence is verified. Authentic owner financial records and long-running
prediction accuracy remain empirical acceptance dependencies; CI fixtures are
software verification, not real company profit or predictive accuracy.

## Rollout and recovery

One consolidated develop pull after final CI. Stop the old local server/worker,
retain a verified backup and explicitly run the existing additive migration command.
Migration039 only extends evidence kinds and adds unique provenance indexes.
Do not reset the organization or drop immutable measurements. Older code cannot
display new workflows; preserve the additive database history when stopping or
rolling back the application. Owner Windows acceptance is a separate local gate.
