# AGO Section 14 — Module Dependency Rules Final Engineering Acceptance

**Scope:** The six checks in the Section 14 subsection of the user's
Sections 1–34 master checklist. **Status:** functional implementation
accepted in isolated GitHub CI. **Out of scope:** all other unfinished
architecture sections, a new distributed microservice stack, deployment
certification and changes to existing business logic.

## Source and verified automated evidence (2026-10-10)

- Functional policy correction commit:
  `af0edb6ad79b39831f781c1bd207e1c947482d4b`.
- Five successful full CI jobs:
  https://github.com/rudrasinha05/ago-/actions/runs/38033460211
- Python 3.11: **272 passed, 0 failed, one known warning**.
- Python 3.14: **272 passed, 0 failed, one known warning**.
- Node 22: **14 passed, 0 failed**, both Python runners.
- Actual Chromium + live FastAPI/PostgreSQL: **6 passed, 0 failed**.
- Non-root hardened Docker smoke: **passed**.
- Actual PostgreSQL 16 dump → manifest hash → separate restore drill:
  **passed**.
- Legacy independent Python 3.12 `Backend quality` workflow repaired,
  supplied isolated PostgreSQL and added the same Section 14 architecture
  gate; separate successful run:
  https://github.com/rudrasinha05/ago-/actions/runs/38033485972
- Python distribution wheel contains the versioned policy JSON and the
  shipped checker is callable with `python -m ago.architecture_guard check`.

## Six individually closed checklist requirements

1. **Owned bounded-context imports:** 76 Python package modules are assigned
   one context and one layer in the source-controlled v1 manifest.
   145 actual AST import edges are explicitly registered, including three
   function-local imports missed by a preliminary line-level inspection.
2. **Forbidden imports/cycles:** exact import approvals, strict layer
   directions, unknown/new modules and imports, nested/relative module
   boundaries, literal/non-literal dynamic imports, self and circular
   dependencies are enforced by the checker. No wildcard exemptions.
3. **Governance/QA owner protection:** direct SQL writers to
   `ago_approval_requests`, `ago_approval_audit` and
   `ago_task_reviews` are locked to the `governance` and
   `quality_store` repositories respectively. Database RBAC, append-only
   and independent-review triggers remain the real runtime authority.
4. **Independent architecture tests/CI:** negative test fixtures exercise
   illegal edges, layer violations, unknown modules, cycles, SQL write
   bypass, stale policy, review expiry and dishonest self-approval. Both
   Python matrix versions run guard and retain deterministic Graphviz
   dependency diagram artifacts; the Python 3.12 secondary workflow
   also runs the guard.
5. **Future extraction contracts:** full architectural obligations for
   synchronous APIs, asynchronous events, tenant security, idempotency,
   retry behavior, schemas, audit provenance, owning services and
   compatible migration are defined in
   `docs/architecture/SECTION_14_MODULE_DEPENDENCY_RULES.md`.
   Nothing was automatically extracted or deployed.
6. **Versioned reviewed exception mechanics:** policy is packaged,
   versioned, source controlled and routed to architecture CODEOWNERS;
   narrowly scoped exceptions require `ARCH-NNN` change request, a
   substantive reason, author, different named reviewer, review date,
   expiry no longer than 180 days and demonstrated actual use.
   Layer/cycle/protected-state violations cannot be waived.

## Governance and technical limitations

- GitHub's `.github/CODEOWNERS` marks architecture ownership, but **branch
  protection requiring code-owner review cannot be certified by this CI
  run**. The repository operator must explicitly configure mandatory PR
  review/checks before treating the reviewer metadata as organizational
  evidence. The checker enforces **declared** author/reviewer distinction,
  not external identity or cryptographic signatures.
- This is static Python AST analysis; runtime authorization, dynamic SQL,
  message broker behavior and policy changes made outside Git remain
  governed by integration tests, PostgreSQL constraints, ops controls
  and human reviews. No universal security certification is claimed.
- Original 0–35 blueprint parity is still unknown because the original
  full source was not imported into GitHub. This report marks **Section 14
  implementation against the user's supplied checklist**, not a claim
  that the entire AGO enterprise architecture is complete.

## Reproduce (source checkout)

```bash
cd apps/backend
python -m ago.architecture_guard check --json --dot section14-dependency-graph.dot
python -m pytest -q tests/test_section14_module_boundaries.py
```

The first command is read-only unless `--dot` explicitly names a local
output file; it does not require DB credentials, migrate SQL, create
accounts or contact external providers. The graph is saved in CI artifacts
for technical review. Future feature authors must update module ownership
through documented architecture review, **not** by weakening this gate.

One `develop` branch retained; no founder Windows pull performed.
