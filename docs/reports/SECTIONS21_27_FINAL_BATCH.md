# Sections 21–27 consolidated local batch

## Acceptance boundary

This implements the frozen **personal localhost, existing architecture, advisory evolution** scope in `docs/SECTIONS21_27_SCOPE.md`. The original blueprint was recovered and read before this batch; its wider production and empirical requirements are not silently redefined as complete. Sections 1–20 interfaces and authority rules remain in force. No user Windows database has been migrated.

Acceptance covers the bounded engineering workflows below, with the wider original gates listed separately. Earlier reports remain historical. A test pass with an absent database is a skip, not database acceptance. The verified source-head CI evidence is recorded below; the closing documentation head is independently verified before operator handoff.

## Delivered workflows

| Section | Result and evidence | Principal acceptance tests |
|---|---|---|
| 21 | Company/department/employee mode and availability controls, exact reviewed HR changes, bounded capacities and reserved lease slots; priority ageing; independently approved offline task claim/run; atomic run/reconciliation prevents replay. Explicit localhost worker revalidates signed sessions and stops on expiry. Lifecycle observations retain task, capacity, queue, restriction and escalation source evidence. | `test_enterprise_capacity_21.py`, `test_enterprise_durable_queue_21.py`, `test_enterprise_hr_21.py`, completion batch owned execution, reservation, intent and local-worker tests |
| 22 | Source-linked assigned/future tasks, hierarchy, dependencies, workload/refusal, permission boundaries, reviewed reported skills/knowledge/confidence/risk/learning, and actual independent QA competence assessments. Unknown mastery/confidence calibration remains unknown. Evidence requests survive reload, and the reviewer sees exact details before deciding. | `test_enterprise_autonomy_21.py`, assistance tests, completion batch competence and pending evidence tests |
| 23 | All nine approved planning horizons, parent/child windows and budget boundaries, strategic DAG/task links, immutable plan revisions with stale-review rejection. Saved descendant rollups include actual QA and public-calendar conflicts and propose human-reviewed replanning. | `test_enterprise_plan_revisions_23.py`, assistance/planning tests, completion batch planning rollup and typed-intent tests |
| 24 | Existing virtual-credit spending guard retained. Separate deduplicated observed cost/revenue claims, governed company/department/employee envelopes, source-linked single-currency incremental ROI and opportunity-cost scenarios with explicit baselines. Invoices and settlement are explicitly unauthenticated. | HTTP/storage/domain economics tests; completion batch finance currency, idempotency and real source-ID tests |
| 25 | Checksum-bound stored bytes; semver/digest dependency and license metadata; publication review can inspect exact pending content. Approved reuse records actual department consumption. Sunset/revocation blocks reuse and reports dependents/consumers and explicit successor/reapproval guidance. No automatic migration or third-party execution. | `test_marketplace_dependency_25.py`, payload tests, completion batch actual stored content/reuse/sunset test |
| 26 | Source-linked actual task/QA diagnostics grouped by employee, department, workflow and handler. Disjoint reviewed task cohorts record hypothesis, observed QA/elapsed metrics, uncertainty and rollback intent. Independently reviewed proposal/outcome history remains advisory. No actual policy/code promotion or deployment. | `test_enterprise_evolution_twin.py`, completion batch actual cohort comparison and exact-digest review tests |
| 27 | Immutable one-way state captures include tenant departments, employees, tasks/strategic lineage, planning, availability, public calendar/deadlines, queue, budgets and cost claims. Freeze a held-out future QA cohort and source digest; compare only later same-cohort independent QA within the forecast window. Wilson uncertainty, Brier/MAE and pending samples are explicit. Existing hypothetical hiring/layoffs/market/budget scenarios remain read-only. | Completion batch held-out forecast/private calendar test; existing Twin scenarios/outcome tests |

Migration `037_enterprise_evidence_snapshots.sql` adds tenant-owned append-only observations, complete-payload digests and independently approved exact-digest reviews. Existing migrations are untouched. The task-review timestamp default records actual QA insertion time without rewriting history.

The Operations & Tools page has guided create/review/apply workflows, saved operation requests, employee evidence, plan revisions, source evidence, forecasts, asset content and impact. Both console and Next.js use canonical UI adapters. Governance looks up a specific approval's complete request directly, independently of the dashboard's pagination. A requester's decision is denied. Structured request approvals cannot be reused with changed parameters via legacy mutation endpoints.

## Limits and remaining original gates

- Genuine provider invoices, real model/storage/tool/time bills, bank/revenue reconciliation and audited real spending/profit remain **operationally blocked** on actual trusted data and connector access. Disposable CI values and operator claims are not financial proof.
- Held-out QA metrics are implemented; statistically established long-run confidence, cycle-time/deadline, revenue/growth and market accuracy remain **unverified** until genuine prior predictions and later observations exist. One successful cohort does not establish general calibration.
- State capture is an explicit, bounded, eventually consistent projection, with capture time/source digest and private-calendar exclusion. It is not continuous synchronized production replication. Queue selection examines a bounded candidate window, not a general distributed cluster scheduler.
- The original full continuously autonomous organization lifecycle, independently validated general agent learning, randomized controlled evolution and broad predictive Twin remain wider **partial original requirements**. The frozen local implementation never changes source, deploys policies or grants authority automatically.
- Owner Windows pull, verified backup, additive migration and local acceptance remain **operator pending**. Production vault, external auditor and cloud deployment stay deferred under the existing personal-use decision.

## Consolidated operator rollout

Use the existing Windows guide and Section 21–27 scope. After final-head CI is green, check worktree/branch, make one `git pull --ff-only origin develop`, rebuild/install using the documented environment, verify a local database backup, stop the old server and explicitly run the normal checksum migration command. Do not reset data, recreate tenants or remove immutable history. Run `python -m ago.local_ops doctor`, restart the existing localhost server and inspect Operations & Tools. Use a distinct real reviewer for operational changes and independent QA after execution.

Optional offline worker (from the existing backend environment, while the localhost server is running):

```powershell
python -m ago.local_ops work --iterations 1
```

It asks for the existing tenant ID and account credentials, holds credentials/token in memory, executes only separately approved `internal:brief` work, and leaves human QA pending. Bounded polling is opt-in with `--iterations` and `--poll-seconds`; authentication failure stops it.

Rollback: stop the new worker/server and use the prior compatible code only after confirming schema compatibility. Migration 037 is additive; do not delete evidence tables or undo reviews in place. Restore a verified pre-upgrade backup into an isolated target if recovery is needed, following the existing tested restore-drill procedure. Never overwrite the user's live database automatically.

## Verification

Source head: `4deb612ab1be75e902f2f7979493913b51b80a65`. Main workflow: [38097668011](https://github.com/rudrasinha05/ago-/actions/runs/38097668011). Independent backend quality: [38097668047](https://github.com/rudrasinha05/ago-/actions/runs/38097668047). Both workflows **SUCCESS**; all eight main jobs and the independent backend job passed on this exact source SHA.

| Gate | Actual result |
|---|---|
| Python3.11,3.14 and independent3.12 | 549 passed on each, one existing Starlette/httpx deprecation warning; actual PostgreSQL, no database skips |
| Coverage | 87.28% overall on3.11; governance90.88%, workforce93.30%, strategy91.64%; all unchanged required floors passed |
| Frontend | 30 browser/device/accessibility cases passed across Chromium, Firefox and WebKit; seven actual signed-session/PostgreSQL Next.js journeys passed |
| Console | Six real Chromium console journeys; canonical generated adapters retained |
| Storage and recovery | Fresh/idempotent checksum migrations, real model/Redis/private bytes recovery, PostgreSQL backup/restore and nonroot Docker smoke |
| Contracts/build/lint | Existing API fingerprints preserved, strict architecture/domain/backend/frontend/monorepo checks, actual Next.js exports and lint |

The completion-batch test file contains22 new cases, including9 typed operation parameter sets. It exercises execution/replay, reservation/recovery, exact approval substitution and self-review denial, immutable source review, actual-QA competence/cohorts, planning hierarchy/assignment feedback, frozen later-outcome metrics, claimed economics and actual stored asset publication/reuse/sunset. Source data generated in disposable CI proves behavior, not real financial results or predictive validity for the owner's organization.

The closing documentation commit changes no execution behavior. Its own final-head CI must also pass before the owner is given the consolidated pull point; exact closing SHA/workflow links are written to the master checklist after verification.
