# AGO Command Center — visual task intelligence upgrade

Baseline: `develop` after the 20 October 2026 founder dashboard requirements. This is a software change record, **not** evidence that autonomous agents completed and published customer projects.

## UI and behavior
- A wide dark command-center banner contains a CSS/SVG 3D-style holographic brain with neural linework, pulse/orbit effects and reduced-motion support.
- The brain panel shows only persisted task states and the latest **recorded** status transitions. It does not expose private chain-of-thought or invent live inference.
- Employee work cards show their actual name, human/AI kind, linked strategy-plan title when present, current running action, persistent event count and a click target.
- Running tasks: vivid red employee-card border; assigned work on other statuses follows amber card style. Assigned reporting edges from the founder along existing manager IDs glow red. Multiple assignees are visualized simultaneously.
- The sidebar shows employee status plus event counts and assignment indication. Clicking employees opens actual task details, reporting manager, department, event history and common accountable responsibilities in the right pane.
- Five board **governance functions** are displayed with responsibilities. Seats remain clearly **not appointed** when the actual organization has no explicit board-membership record. This panel does **not** confer governance permissions.
- Durable notification counts come from `ago_company_chat` rows whose `kind='status'`. Each task transition is persisted by migration 048's existing trigger; the new authenticated tenant-scoped `GET /v1/organization/company/notifications` API supplies counts and latest 100 events. The browser polls and queues new events as transient popups. Counts are cumulative work-event counts, not unread badges; old missed popups remain in durable history. The latest 100 are a bounded window.
- GitHub workspace reads actual reviewed project bindings from `/v1/platform/catalog` and calls existing GitHub project-status APIs. It indicates absent bindings, inaccessible status or runtime configuration honestly instead of claiming a sync happened.
- Reporting and publishability expectations are displayed. They remain company policy guidance: final quality, real agent autonomy and releases still depend on configured runners, authorizations, QA and real GitHub evidence.

## Source
- `apps/web/components/company-map.jsx`
- `apps/web/components/command-brain.jsx`
- `apps/web/app/workspace.css`
- `packages/sdk/company.js`
- `apps/backend/ago/company_chat.py`
- `apps/backend/ago/api_company_chat.py`
- `apps/backend/ago/repository_ports.py`
- API and repository contracts plus regression tests.

## Acceptance gates
1. `npm ci && npm test && npm run build` — JS model helpers and Next.js build.
2. `python -m ruff check ago tests` and `python -m pytest -q` in `apps/backend` with disposable PostgreSQL for DB-backed tests.
3. `python scripts/check_engineering_quality.py` at root — strict baseline drift policy.
4. Browser: visit `/workspace/organization/` in signed-in dev environment; verify active red routes, busy red card, counts, details, chat persistence, project titles, board vacancies, motion-reduction option and phone layout.
5. Verify GitHub checks on the **same final commit**; no earlier green checks substitute.

## Important boundaries
- The interface remains a visual monitoring/control surface, not an autonomous always-on thinking process.
- There is no authoritative board appointment and no independent employee-role title column in the existing M2 data model. The UI does not invent either.
- A linked project title means strategy-plan linkage; GitHub project binding is a separate reviewed entity. It is not safe to equate the two silently.
- GitHub credentials in ChatGPT are not injected into AGO backend. AGO backend's token/tenant ID must be configured through approved local operations.
- Real publishability requires working implementation, independent QA, reproducible builds, complete documentation, security gates, release approval and evidence; the UI cannot replace these.
