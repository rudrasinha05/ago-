# BDR — One Section, One Complete Delivery

**Governance status:** Standing project engineering rule requested by the
founder (2026-10-10). Applies to the entire AGO architecture Sections 1–34,
including future approved sections, regardless of milestone labels M0–M20.

## Non-negotiable delivery sequence

1. **Source verification first.** Read the original applicable architecture
   section and the user-maintained 1–34 checklist, verify existing code,
   cross-references and blockers. If the original full section text is not
   available, disclose that limitation and use only the supplied checklist
   as the bounded scope; do not invent an authoritative specification.
2. **Freeze one section's acceptance criteria.** List every independently
   testable subrequirement, concrete artifacts, dependency decisions and
   negative tests before modifying implementation. Resolve contradictions
   in review, not during unapproved implementation.
3. **Implement the entire section in one coordinated batch.** Include
   interfaces, domain behavior, persistence only when needed, authorization,
   UI only when needed, documentation, failure paths and migration/rollback
   plans within the section's defined scope. Do not divert into unrelated
   modules or claim work that was only described.
4. **Integration, not isolated demos.** Reuse AGO's existing modular
   monolith, single `develop` branch, signed sessions, database,
   independent human approvals and audit rules; do not create new
   databases/services without a separately approved architecture decision.
5. **Acceptance is test evidence.** Add targeted positive/negative tests,
   run Ruff, Python matrix, JavaScript/browser tests when relevant, Docker/
   migration/backup gates where impacted. Check the final commit's actual
   green CI logs. Broken unrelated CI gates must be recorded and fixed before
   claiming entire project CI acceptance.
6. **Close all in-scope checkboxes together.** A section is not **fully
   implemented** if any requirement is absent or unverifiable. If a
   production/provider/human-controlled gate cannot be completed with
   current access, mark `Implementation complete — operationally blocked`
   and state the exact dependency; never rewrite the criterion or invent
   success. Partial progress is reported, not presented as completed.
7. **Update the single source of progress truth.** Publish the source
   commit, CI run, acceptance report and Section 1–34 checklist status;
   distinguish architecture documentation from executable functionality.
8. **One local pull per agreed batch.** Never ask the founder to repeatedly
   sync, run migrations, clean untracked files or change environment during
   implementation. The founder alone initiates a consolidated local
   verification and production/cloud deployment steps.
9. **No mid-section scope creep.** Additional ideas go into the backlog,
   with dependencies and separate approval, rather than extending active
   section work indefinitely.
10. **Stop before the next section.** Finish the current section's declared
    acceptance and evidence first, then select the next by dependency and
    impact; do not simultaneously leave multiple sections half-implemented.

## Meaning of section statuses

- **Not started:** requirements identified, no implementation commenced.
- **In progress:** at least one gate incomplete or red; never call complete.
- **Implementation accepted:** bounded code/docs/tests green, but an external
  operational gate may still be pending; enumerate that pending item.
- **Fully accepted:** every scoped functional, security, integration,
  documentation **and applicable external** acceptance gate verified.
- **Documentation only:** original section explicitly defines specification
  rather than deployable business logic; source fidelity and review required.

## First application: Section 14

The implementation/test side of Section 14 is CI accepted:
76 registered modules, 145 strict imports, zero violations, documented
service-extraction contracts and negative guard tests. CI evidence and
exceptions are recorded in
`docs/reports/SECTION14_FINAL_ACCEPTANCE.md`. CODEOWNERS exists; **actual
GitHub required independent review/branch protection is not verified**.
Do not represent this external setting as complete. Every other
architecture section remains separately tracked.

This BDR delivery rule supplements, and does not replace, the original
1–34 enterprise architecture or any higher-priority constitutional rule.
