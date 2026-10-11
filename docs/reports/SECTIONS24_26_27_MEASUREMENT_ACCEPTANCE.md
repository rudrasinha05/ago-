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

## Implemented workflows

All ten additive workflows are under `/v1/operations/enterprise/measurements/`
and are available through **Organization workflows** in the existing Operations
screen. The canonical Next.js and compatibility console share the same actions,
source preview/download, independently reviewed evidence rows and measurement tables.

- **economic-period** freezes selected reviewed reconciliations, unique cost IDs,
  exact period/currency, category totals, selected independent QA cohort and optional
  approved company budget. Costs cannot be reused in another period. Missing
  costs, missing revenue and absent QA are unknown; an explicit recorded zero
  remains distinguishable. Budget variance does not authorize additional spending.
- **economic-study** freezes an observed baseline, a future candidate period and
  the exact unapplied governed change intent, hypothesis and rollback. The study
  must receive independent review before candidate observations. **economic-comparison**
  compares observed periods, optional measured alternative, daily net value,
  incremental ROI, cost savings and QA/budget/category safeguards. An intervention
  audit requires actual reviewed application of precisely the frozen intent.
  Partial or regressed safeguards retain the baseline/require more evidence.
  This is descriptive accounting; risk, strategic value and counterfactual
  comparability remain human-reviewed context. No payment, change or promotion occurs.
- **quality-subject** stores immutable exact bytes and version for prompts,
  architectures, workflows, departments or employees. **quality-study** requires
  two independently reviewed different versions of the same subject and freezes
  weighted rubric, expected sample quota, sampling plan, hypothesis and rollback.
  **quality-sample** retains actual source/output bytes, time, version, scores and
  rationale; independent source/score review is mandatory before measurement.
  Reused output bytes, duplicate source references, changed retries, pre-review
  observations and quota extensions are denied. **quality-report** records weighted
  scores, baseline/candidate deltas, descriptive uncertainty, missing/unreviewed
  samples and exact approval/digest lineage. This supports arbitrary supplied
  source artifacts; human rubric scores do not certify provider execution,
  general architecture superiority or causality.
- **metric-outcome** binds a stable dimension/metric/unit/entity and completed
  period to actual reviewed records. Cost and revenue derive only from reviewed
  company economic periods; total_cost/total_revenue or exact expense-category
  definitions prevent a total from being mislabeled as a category. Missing
  categories cannot become zero observations. Growth/market/risk/headcount
  records require exact source bytes and explicit methodology; risk and headcount
  values have additional bounds. Same-series overlapping actuals are denied.
- **longitudinal-forecast** freezes model version, complete Twin snapshot,
  future series periods, predicted values, intervals and their basis, assumptions,
  sensitivity factors and already reviewed historical-source digests. Future
  outcome periods cannot be enrolled retrospectively. **longitudinal-calibration**
  matches later independently reviewed exact-series/unit/period outcomes across
  one model version. MAE, RMSE, signed bias, empirical interval coverage, pending
  and overdue outcomes are explicit. Forecast review must predate each target
  period. Changed same-key retries cannot rewrite either forecasts or reports.

Periodic OOS diagnostics ingest only independently reviewed comparison/calibration
reports, retain every latest quality dimension and expose unmeasured dimensions.
Twin captures project the latest reviewed business series with source digests,
units, periods and approvals. Analytic history scans exclude large source-byte
copies; original bytes remain immutable and available for human source review.
Bounded history caps fail visibly rather than silently accepting truncated data.

## Personal localhost usage

1. Record actual expense/revenue claims; attach exact invoice/bank sources, obtain
   independent review and reconcile them. Review the reconciliation itself.
2. Measure and independently review an economic period. Select the real QA cohort
   and its period allocation; absent values stay unknown.
3. For an improvement, save its governed request without applying it, register the
   future economic study and obtain independent review. Apply only through the
   existing approved operation. Later review the actual change evidence and
   candidate economic period, then compare. Retain all rollback/audit references.
4. Store/review quality subject versions, register/review a rubric study, record
   source-backed scores and independently review each sample before comparing.
5. Capture Twin state, freeze/review future business forecasts before target periods
   start, then record/review later actual outcomes and measure prediction accuracy.

Source review/download shows exact original bytes. Scoring, provider references,
zero-value financial claims and model assumptions must be supported by the owner;
the software never creates those business facts or silently requests a paid model.
Two distinct human accounts retain the existing review boundary.

## Acceptance evidence and limits

The exact final develop SHA, all nine job conclusions, backend Python3.11/3.12/3.14,
coverage, JavaScript/SDK, Next.js/Chromium, migrations/restore and architecture checks
are written to the single `AGO_Architecture_Sections_01_34_Master_Checklist.md`
after the final head's CI succeeds. Older green runs cannot accept later code.

Targeted acceptance covers all five quality dimensions, complete/missing expense
categories, measured ROI and budget variance, exact actual intervention lineage,
financial and nonfinancial longitudinal outcomes, unknown training and future
actuals, duplicate/mixed-period sources, immutable records, signed RBAC, cross-tenant
isolation and exact human source review in the shipped Next.js UI. Disposable
logical-clock test periods validate chronology guards, not actual company economics.

All six measurement workflows are implemented. Authentic owner expenses/value,
real financial reconciliation/optimization outcomes and longitudinal business
accuracy remain real-use acceptance dependencies. The broader quality measurement
mechanism is implemented; any claim that a particular prompt or architecture is
superior still requires genuine comparable samples and independent evaluation.
Windows backup/pull/migration039/doctor/local acceptance has not been performed.
