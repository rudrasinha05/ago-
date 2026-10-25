# AGO Founder-reviewed AI leadership setup

The actual laptop diagnosis reports a valid linked Founder discovery and approved
task, but five required Board appointments are missing. The Founder can use the
existing AGO API to fill actual software AI employee roles, not legal directorships.

With the local server running, from repository root:

    python .\scripts\ago_company_setup.py --scope core --create-missing

This is a READ-ONLY preview of exact role titles, responsibilities, reused AI
employee IDs and missing identity records. After reviewing, run:

    python .\scripts\ago_company_setup.py --scope core --create-missing --apply

Provide the existing Founder organization ID/email/hidden password; type the
confirmation APPOINT_AGO_AI_LEADERSHIP only if every assignment is correct.

Core provisions CEO, CTO, CFO, CISO, CQO, and their existing five governance
seats. Full optionally includes seven *non-Board* AI functions: COO, CAIO, CPO,
CMO, CHRO, Chief Research Officer and CLO. Preview extended scope first:

    python .\scripts\ago_company_setup.py --scope full --create-missing

An optional local JSON file can map exact existing AI employee UUIDs to role
codes such as CEO, CTO, CFO, CISO and CQO using --assignments. The script
prefers uniquely matched existing AI employees and will not invent human skills,
use humans for the AI Board, recycle one person across two seats, overwrite an
already filled seat, or silently override meaningful prior responsibilities.

Only existing AGO authenticated localhost APIs are called. A newly created AI
employee is a software role record, not a real autonomous worker, qualified
human officer or automatically authorized agent. Role titles never grant RBAC.
There is no model call, task execution, payment, migration, GitHub push,
QA verdict or product release.

After any partial network failure stop; inspect current Board and re-run the
read-only preview before applying again. A lost POST acknowledgement may mean
that its change was already persisted.

The seven-role run additionally needs an *existing project-specific* AI PM
and worker, with a valid reporting chain and Founder-approved discovery task.
The script intentionally does not mutate those project-specific links. Check
the original task by using the read-only command:

    .\scripts\ago.ps1 diagnose-approved-engineering

Then enter its old task UUID. NEVER retry the original attempted run. Future
execution requires a new, separately Founder-approved task.
