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
An AI member may recommend approve or deny through a genuine approved model-run artifact.
Making those recommendations into scoped, recorded Board votes with executable consequences remains a separate workflow. Nothing in this batch claims it is finished.
Founder final project release and security controls are unchanged. This is a functional AI-company organization under construction, not a market-ready fully autonomous company.

## Windows VS Code operator

From your existing AGO repo PowerShell terminal:

    cd C:\Users\rudra\Projects\ago-
    .\scripts\ago-sync.ps1
    $env:AGO_FOUNDER_SOLO_APPROVAL = 'true'
    .\scripts\ago.ps1 doctor
    .\scripts\ago.ps1 serve

Never paste credentials into chat; do not run migration or initialize a new tenant merely to enable the mode.
Do not start cloud services, reboot or wake the laptop, or create a second fake reviewer identity.

## Acceptance

Check current develop CI: backend quality, full nine-job matrix and the focused company-growth tests.
Run authenticated founder-only local smoke tests and genuine model/Board workflow on the founder's laptop.
Board voting, trusted AI approval evidence, end-to-end engineering and real GitHub release stay separately pending.