# AGO M6 — Backend Milestone Acceptance

**Status: M6 backend operational vertical slice ACCEPTED in GitHub CI.**
This is not a production-release approval and not a claim that all Sections
0–35 of the Artificial General Organization blueprint are implemented.

## Verified acceptance evidence
- Source commit: `db1ca9a922ae776626b11071dc7b988843c5ec3d`
- Passing GitHub Actions run: https://github.com/rudrasinha05/ago-/actions/runs/38016243167
- Python **3.11: 155 passed, 0 failed, 0 skipped, 1 nonblocking warning**.
- Python **3.14: 155 passed, 0 failed, 0 skipped, 1 nonblocking warning**.
- PostgreSQL 16 isolated CI database: all ordered migrations **001–015 applied**.
- `python -m ruff check ago tests`: **All checks passed**.
- Tests include signed-session HTTP flows, independent reviewers, council quorum
  plus M2 approval, tenant isolation, role revocation, event privacy,
  knowledge reviewer separation, database immutability, and deterministic audit
  history order. Existing 143-test M1–M5 regression suite remains green.

## Six completed gates
1. **Cross-department handoffs**: source and receiving departments, idempotent
   requests, independent active-human acceptance, terminal evidence and history.
2. **Organizational calendar**: timezone-aware range validation, tenant/private
   visibility, invited-employee responses, creator cancellation and append-only
   event logs; does NOT email or invite anyone outside AGO.
3. **Knowledge graph**: typed nodes and edges, mandatory source references,
   independent active human review, verified-only standard feeds, restricted
   pending queue, immutable reviewed content and composite tenant FKs.
4. **Executive council**: proposal records, at least two independent human
   voters, immutable ballots, negative-vote rejection, independent M2 human
   consent before passing, database quorum enforcement, advisory-only results.
5. **Secure APIs and role administration**: /v1/operations, /v1/knowledge and
   /v1/council integrated in FastAPI with signed sessions and persistent RBAC;
   existing tenants require explicit operator-approved M6 role grants.
6. **Audit and integration**: database constraints/triggers, event-order
   sequences, full HTTP and PostgreSQL integration tests on Python 3.11/3.14.

## Explicitly outside this acceptance
- The founder's Windows PostgreSQL 18.6 has **not yet been locally verified for
  M6**; new migrations 012–015 require one founder-initiated local pull/migrate.
- Executive council passage does not execute tools, grant permissions or change
  policy; consequential actions always need separate M2 review.
- No production mail/calendar sync, GUI, autonomous management, generalized AGI,
  external agents, cloud runtime, secret vault, backup/restore certification,
  least-privilege database deployment, performance/load or external security audit.
- Source references and human approval do not establish that a fact is objectively true.

M6 operator guide: `docs/reports/M6_OPERATOR_GUIDE.md`.
BDR: all code remains on the single `develop` branch; no intermediate local
pull was requested.
