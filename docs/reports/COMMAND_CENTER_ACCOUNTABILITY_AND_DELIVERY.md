# AGO accountability, reporting and delivery — October 2026

## What the founder can do
- Work on `develop` while `main` remains reserved for explicit accepted releases.
- Open Company Map to see employee status, current linked project title, red active routing, persistent work-event badges and actual recorded events.
- Assign descriptive role titles, core responsibilities and additional duties to real employee IDs. These do not grant execution permissions.
- Explicitly appoint personnel to five named Board governance seats. Appointments remain empty until founder action. A Board seat is a responsibility label **not** a GitHub, legal, financial, or RBAC privilege grant.
- View the governed GitHub project status when a real project binding, tenant credentials and reviewed operation exist.
- Override or interrupt via existing controlled task/governance workflows, not through unreviewed code or hidden privilege escalation.

## What an authenticated human employee can do
- Submit `doubt`, `blocker`, `module_complete`, or `phase_complete` via the Company Map.
- The service computes the recipient from the actual manager ID; if the employee has no immediate manager it selects the active human founder. Founder cannot send a report to self.
- Supply an optional task ID only for a task actually assigned to the author. A retry operation key cannot change an existing report.
- Read own sent reports and reports received. Founder can inspect company-wide. Other employees cannot view private report body through a tenant-visible chat feed.
- Reports are append-only. The tenant-visible work-event feed contains only a notification that a report was submitted, not its body.

## Counted events
Persistent per-employee counts include recorded task status changes, staffing records, upward reports, independent QA outcomes and only **successful** reviewed GitHub operation receipts. Documentation receipts are classified separately when approved commits include `docs/` files. Each event is associated with an employee identity and a tenant; the browser polls to surface new durable events as popups. Missed short-lived popup animations do not erase database events. Counts are cumulative, not unread counts.

## Local developer procedure
1. Pull `rudrasinha05/ago-` `develop`; back up the local developer DB.
2. From the backend directory and against a test PostgreSQL instance, run `python -m ago.event_runtime migrate`. Migration `049_company_accountability.sql` adds role fields, reviewed board-seat records, append-only employee reports and QA events.
3. From repository root run `npm ci && npm test && npm run build`, then `python scripts/package_frontend.py`.
4. Run the existing signed-in AGO local server, then open `/workspace/organization/`.
5. Check the exact same SHA in GitHub Actions, browser artifacts and migration regression. No real founder or service credentials should appear in reports.
6. For actual remote GitHub work, separately configure AGO tenant-bound connector settings and the existing independently reviewed Section34 GitHub lifecycle.

## What is **not** proved
- Continuous autonomous thinking, employment or real-world board appointment authority;
- Independent agent software engineering of arbitrary user prompts;
- Fully automatic repo publication, Play Store/market launch, billing or external audit;
- Browser polling when the app/server is closed or machine sleeps;
- Complete market-ready output without verified QA, security and owner release gates.

A startup project is **not marked publishable merely by a green dashboard**. External credentials, operational uptime, authorized model tooling, independent review, and a real end-to-end project release demonstration remain required.
