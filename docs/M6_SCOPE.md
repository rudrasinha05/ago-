# AGO M6 — Organizational Collaboration & Institutional Knowledge

M6 is the next **backend operational vertical slice** in the approved Sections 0–35 modular-monolith architecture. It extends, not replaces, M1–M5. The entire commercial AGO platform, GUI and provider marketplace are not part of M6 acceptance.

Six locked M6 gates (BDR):
1. **Department coordination:** tenant-safe handoff requests, independent receiver acknowledgement, work evidence and lifecycle.
2. **Organizational calendar:** scheduled/cancelled events, associated goals/tasks, participants, visibility controls, no automatic external invitations.
3. **Knowledge graph:** source-backed knowledge nodes, typed relationships, pending-to-reviewed human verification, cross-tenant denial and immutable evidence.
4. **Executive council:** authenticated human votes, configurable quorum, append-only ballots, independent M2 human approval before a motion can pass.
5. **Operating APIs:** signed sessions, persistent RBAC for all reads/writes, scoped queries and safe audit.
6. **Acceptance:** disposable PostgreSQL migrations, negative/security tests, integrated HTTP regression, Python 3.11 and 3.14 CI; exact passing proof.

Security boundaries:
- Council motion passage is **advice / governance record**, not authority for external execution. Every consequential action still requires its own M2 task approval and trusted adapter.
- Knowledge review verifies recorded evidence/reviewer, not factual truth. Knowledge may not silently rewrite policy or constitutional rules.
- Calendar only stores records; no email, notifications or auto-attendance.
- Handoffs are organizational state transitions, not physical task execution.
- Roles: operations:write/read; calendar:write/read; knowledge:write/read/review; council:propose/vote/read/finalize.
- No scope changes or extra branches; `develop` only. One consolidated local pull only when founder explicitly requests it.
