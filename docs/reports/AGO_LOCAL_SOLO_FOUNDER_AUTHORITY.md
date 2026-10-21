# AGO — Sole-Founder Local Governance Contract

Owner direction: one human founder, real hierarchical AI-company staff and existing appointed Board.

## Implemented decision lane

- Founder is the only required human for local operational approvals when no other active human approver exists.
- Opt in explicitly with AGO_FOUNDER_SOLO_APPROVAL=true in the same terminal as the server.
- Runs only when AGO_ENVIRONMENT is development/testing/test (or unset), not in production/staging.
- The real active human founder identity, tenant, currently pending request, decision reason and immutable audit remain enforced.
- If another active human with approval:decide exists, ordinary independent review is required.
- Strategic founder-only reviews remain founder-only. QA cannot be falsified by self-reviewing one's own work.
- Disabling the flag immediately removes the local override; the stored decision history remains.

## Board responsibilities and limitations

Current Board appointments are durable company role records, not actual approval permissions by themselves.
AI Board members have no human login or power to approve protected operations using forged credentials.
In the local Ollama CEO/CTO chain, an explicit single BOARD_RECOMMENDATION line produces a stored, nonbinding approve/deny recommendation linked to that real employee and task run. An absent/ambiguous line remains unverified.
Actual permission-bearing Board votes, Finance/Risk/Quality seats, and executable consequences still require separate scoped authorization and evidence. This batch does not grant those powers. Nothing in this batch claims it is finished.
Founder final project release and security controls are unchanged. This is a functional AI-company organization under construction, not a market-ready fully autonomous company.

## Windows VS Code operator

From your existing AGO repo PowerShell terminal:

    cd C:\Users\rudra\Projects\ago-
    git status --short       # confirm no pending edits first
    git switch develop
    git pull --ff-only origin develop
    # ago-sync.ps1 arrives with this pull; use it for LATER updates only.
    # Only after an authorized local database backup, apply new migration 060:
    .\scripts\ago.ps1 migrate    # explicitly type MIGRATE when prompted
    $env:AGO_FOUNDER_SOLO_APPROVAL = 'true'
    .\scripts\ago.ps1 doctor
    .\scripts\ago.ps1 serve

Never paste credentials into chat. The earlier solo-approval API needs no database
migration by itself, but *new Quality-stage activation* requires reviewed migration
060. Back up the existing local database before applying it; keep your tenant and
other records untouched. Never initialize a replacement tenant to enable this mode.
Do not start cloud services, reboot or wake the laptop, or create a second fake reviewer identity.

## Acceptance

Check current develop CI: backend quality, full nine-job matrix and the focused company-growth tests.
Run authenticated founder-only local smoke tests and genuine model/Board workflow on the founder's laptop.
Board voting, trusted AI approval evidence, end-to-end engineering and real GitHub release stay separately pending.
## QA ownership when the founder is the only human

In explicit sole-founder local mode, Quality stage can nominate the active human founder only if a different actual employee is the accountable delivery manager. The founder can review an AI worker's actual finished task under existing qa:review and author/reviewer separation, without a fake reviewer identity. The model's Board advisory is never an automatically passed QA verdict. Founder-as-delivery-manager still leaves a Quality staffing conflict visible.

## Board denial as a bounded workflow hold

A verifiable CEO/CTO local Ollama BOARD_RECOMMENDATION: DENY is recorded as nonbinding advisory evidence, but immediately stops further AI handoffs in that internal run. No CTO/PM/worker draft is fabricated after a CEO denial; no PM/worker is invoked after a CTO denial. The founder sees the objection and may choose a newly governed corrective action. Missing or ambiguous recommendations remain unverified rather than falsely authorized. No external release or GitHub side effect is authorized by this hold.

## New company onboarding only

For a **brand-new** empty local organization, AGO also offers a separate `init-solo` path. After setting the explicit environment flag and verifying local migrations, run `./scripts/ago.ps1 init-solo` to create exactly one authenticated human founder, without a fictional reviewer. Existing `init` still uses the legacy two-human model. **Never run `init-solo` for the current existing AGO organization**: it creates a separate tenant and does not migrate historical projects.

## Legacy Quality staffing backlog

For an unstaffed Quality stage created before enabling sole-founder mode, the read-only management workload can now recommend the real founder only when the local policy is eligible and a different employee is the accountable delivery manager. The suggestion cannot appoint itself, approve execution, claim QA pass or create a reviewer identity. Independently authorized existing human reviewers keep their normal lane.

## Approval replay protection

The stage activation service reads the actual recorded approval decision author. For self-approved sole-founder local proposals, it re-verifies active human founder eligibility and the local opt-in **again at activation**. Changing the server to production or disabling the option after approval blocks new stage activation; no approved request is silently replayed into a broader environment.

## Five-seat Board review (explicit local opt-in)

Set `AGO_LOCAL_FULL_BOARD_REVIEW=true` alongside `AGO_LOCAL_COMPANY_CHAIN=true`
and `AGO_LLM_PROVIDER=ollama_local` in the SAME backend terminal. Only
development/test environments can use the seven-role path. No cloud or new
service is started automatically.

Before task execution the existing approved founder-owned discovery task must
be linked to exactly **seven distinct real AI employees**: founder-appointed
Strategy & Vision (CEO), Technology Oversight (CTO), Finance & Budget,
Risk & Compliance, Quality & Release, then the real project manager and
assigned AI worker. A missing or duplicate seat causes preflight refusal;
no credits or task status are consumed.

The bounded local Ollama chain executes each Board seat in the fixed order.
Every Board output must explicitly contain one verifiable
`BOARD_RECOMMENDATION: APPROVE` line to reach the next seat and the
PM/worker. An explicit `DENY` or missing/ambiguous line stops downstream model
calls, records the responsible seat and a founder-visible review hold.
Board votes remain **AI advisory decisions**, not human authentication,
automatic GitHub approval, production authorization, QA verdicts, payments or
release. The run reserves seven **virtual** model-attempt credits; a held run
does not refund the unused reservation. Real provider usage is separately
resource-bound.

The older two-seat CEO/CTO path remains the default when the opt-in flag is
not set, preserving existing localhost setups. Full Board execution and
reviewed code delivery are deliberately separate achievements.

## Board hold is a task blocker, not an accepted deliverable

When an approved AI Board inference returns a DENY or an unverified verdict
in full-board mode, the real governed **task** ends as `failed` (delivery
blocked); the actual local model-attempt run ends as `completed` because the
inference and its persisted evidence completed. Its API response reports
`delivery_status=blocked`. A failed task cannot receive a passing QA verdict
under the existing TaskStore/QualityStore gates. Manager reporting emits a
durable `blocker` instead of incorrectly reporting `module_complete` once
reviewed migration 061 is applied. Any corrective action needs a new approved
task; no automatic re-run or Board override is performed.
