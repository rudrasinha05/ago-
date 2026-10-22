# AGO Approval Authority Compatibility Audit — 23 October 2026

## Scope and evidence

Source of truth: `develop` at `068405d0a7c40e2a380b1e1382e4610b2df2e5c9`. No claim of a successful same-head full CI run. This report is an analysis of the current behavior and a migration acceptance contract, **not an approval-policy implementation**.

- [CI run 39845326058](https://github.com/rudrasinha05/ago-/actions/runs/39845326058): Section 28 native graph comparison **7 passed**; Section 30 temporal governance **14 failed, 60 passed**.
- Historical full backend CI [39842861340](https://github.com/rudrasinha05/ago-/actions/runs/39842861340): **130 failed, 765 passed** under Python 3.11; same-HEAD result after further edits not established here.
- Source: `apps/backend/ago/governed_execution.py` (`GovernanceGate.decide`) admits only an authenticated active human Founder for human approvals.
- Source: `apps/backend/ago/governance.py` (`ApprovalRepository.decide`) checks the stored action scope and enforces an active human Founder. Bounded CEO project task/stage reconciliation uses separate repository methods.
- Source: `apps/backend/ago/calendar_store.py` (`CalendarStore.apply_governance`) currently rejects the calendar proposer as the same approval reviewer and checks that the independent approver is an active human with `approval:decide`. Calendar policy validation also checks listed human reviewers.
- Source: `apps/backend/tests/test_section30_calendar.py` asserts the older independent-human decision contract and therefore conflicts with the changed central human-decision gate.

## Approved authority boundary (do not silently change)

1. **Founder:** defines and approves a complete project scope and retains constitutional, strategic, and exceptional human decisions. The active authenticated human identity is checked server-side, never inferred from UI labels or caller-provided flags.
2. **CEO:** can coordinate the five project stages and verify specifically recorded internal work **only within the exact Founder-approved scope** using bounded, auditable endpoints. This is not blanket external-tool, payment, publication, hiring, or production deployment permission.
3. **Research/Architecture/Development/QA/Release staff:** execute appropriately authorized tasks. Development assignee must be distinct from QA assignee where a real QA role exists.
4. **Independent QA / risk expertise:** remains a source of evidence, test verdicts, and recommendations; it must not silently become a second general-purpose Founder approval authority. Whether a constitutional amendment or particular regulated action requires an additional independently authorized human decision is a separate explicit governance requirement.
5. **Audit/tenant controls:** immutable decision history, signed sessions, tenant isolation, replay prevention, and reviewer evidence must remain enforced. Avoid converting a red security test to green by skipping it, replacing its expected status without validating the authority path, or weakening database constraints.

## Actual blocking contract mismatch

| Component | Enforced current behavior | Conflict |
|---|---|---|
| M2 `GovernanceGate.decide` | Founder-only human decision | Older operational tests invoke the separate reviewer |
| Calendar `apply_governance` | Approved calendar record must be decided by a *different* active human reviewer from the original Founder proposer | Central endpoint allows only Founder to decide, so the same valid approval cannot pass calendar's independent gate |
| Calendar `_human_available` | Active human reviewer with `approval:decide` | Founder-only decision does not automatically prove the independent reviewer is available |
| Section 30 tests | Independent reviewer approves, Founder proposer applies | Fails at general approval decision or, with Founder self-decision, fails at calendar apply |
| Company project-scoped CEO reconcile | Bounded CEO verifies in-scope tasks/stages | Must remain separate from calendar/constitutional authority |

**Conclusion:** Merely changing a Section 30 test's reviewer to Founder is not a repair: calendar apply will reject a same-person reviewer. Merely restoring non-Founder access to the generic M2 decision endpoint violates the currently adopted Founder-only model. This is a genuine cross-subsystem design reconciliation, not just a stale fixture rename.

## Required resolution sequence

- [ ] Preserve original calendar tests and classify each assertion as (a) Founder final authority, (b) separate calendar evidence/recommendation, (c) exact plan/task authority, or (d) independent legally/constitutionally required review.
- [ ] Specify an explicit durable distinction between **recommendation/attestation** and **authorization** for calendar governance, or explicitly approve a narrowly limited exceptional authority route where truly required. No generic reviewer fallback.
- [ ] If calendar requires distinct evidence, create a separate tenant-scoped review/attestation record with actor, scope, digest, status, timestamps, and immutable audit. Do not pretend that the Founder approval row is a separate person's QA verdict.
- [ ] Apply any schema change as a new reviewed forward-only migration. Preserve existing history and add a safe transition for already pending review records.
- [ ] Add positive and negative real-PostgreSQL tests for independent evidence (when required), Founder authority, CEO overreach, unapproved work, cross-tenant access, replay, stale revisions, inactive staff, and direct database bypass.
- [ ] Reconcile calendar and historical backend tests against the approved new service contract, retaining substantive assertions and full suites. No pytest skips/xfails or arbitrary relaxation of authorization.
- [ ] Verify focused Section 28+30 and complete Section 1–M12, Python 3.11/3.14, browser and accessibility jobs all green **on the same `develop` commit**.
- [ ] Separately verify local PostgreSQL migration and signed-in browser flows. No cloud hosting is necessary for this owner's current laptop-only AGO use.

## Exact acceptance target

Founder approves authorized scope once; CEO and qualified staff coordinate and execute only bounded in-scope work; independent QA evidence is available and accurate; no unauthorized account can approve, impersonate QA, expand scope, access another tenant, or bypass immutable history. All relevant database, unit, security, and real-browser tests must pass together.

**Current status:** Open / implementation and complete-CI verification pending. No claim of production release, external audit, or autonomous software publishing.
