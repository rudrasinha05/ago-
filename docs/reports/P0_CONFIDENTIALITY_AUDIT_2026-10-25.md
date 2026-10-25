# P0 confidentiality audit — #133, #134, #156

- **Repository:** `rudrasinha05/ago-`, branch `develop`, commit `f056b53` (2026-10-25)
- **Method:** source reading only. No code was changed and no test was run (the sandbox cannot install Python packages). Every finding cites a file and line in that commit.
- **Ledger status:** unchanged. #133, #134 and #156 stay **Partial** until same-SHA CI and the Windows check below are evidenced.

## Remediation status (develop)

| # | Status | Change | Evidence available here |
|---|---|---|---|
| F1 | Fixed in source | `GoalStore.list` / `PlanStore.list` take `reader_id`; a founder-intake goal or plan shows its title and description only to that founder (`founder_confidential` flag otherwise). The stored data and the Approval Inbox excerpt are unchanged, so no backfill migration was needed. | SQL run on PostgreSQL 16 with all 65 migrations; extended `test_confidential_registry_denies_unassigned_company_readers` (PostgreSQL, CI) |
| F2 | Fixed in source | `source_outcomes` keeps ids, status, review fields, `experiment` metadata and `result_sha256`; never the result body. | Helper unit checks; extended experiment test (PostgreSQL, CI) |
| F3 | Fixed in source | The bulk evidence list drops `content_base64` (top level and inside `intent`) and sets `content_withheld`, matching `_measurement_rows`. Approval details still show one item to the reviewer. | Helper unit checks; extended financial-document test (PostgreSQL, CI) |
| F4 | Fixed in source — operationally blocked | `release_ops.restrict_to_owner` applies `chmod 0600` on POSIX and an owner-only `icacls` ACL on Windows; backup and manifest fail closed if protection fails. | 3 new tests in `test_m10_release_ops.py` pass locally (Windows path simulated). **Needs one real Windows run on the founder laptop.** |
| F5 | Fixed in source | GitHub-project proposals pin the goal by `description_sha256` instead of copying the description. Proposals stored before this change still verify through the legacy row shape. | SQL hash matches Python SHA-256 on PostgreSQL; extended GitHub-project test (PostgreSQL, CI) |
| F6 | No change (accepted, low) | Every application error message raised in `apps/backend/ago` is static; library `ValueError`s can only echo the caller's own input back to that caller. Changing all details would alter user-facing errors without a confidentiality gain. | Source review below |

## Summary

| # | Severity | Where the private data goes | Who can read it | Ledger task |
|---|---|---|---|---|
| F1 | Medium (latent) | Full founder brief copied into `ago_goals.description` | Anyone holding `brain:read` via `GET /v1/brain/goals` | #133, #156 |
| F2 | Medium | Full agent-run `result` copied into experiment evidence | Anyone holding `operations:read` (reviewer role has it) | #133, #156 |
| F3 | Medium (needs your decision) | Raw invoice / bank document bytes stored in evidence and returned by the list endpoint | Anyone holding `operations:read` | #156 |
| F4 | Medium (Windows only) | Backups and local receipts protected only by POSIX modes | Other Windows accounts, depending on the folder's ACL | #10, #156 |
| F5 | Low | Full goal row (including brief) embedded in GitHub-project integration proposals | Anyone holding `approval:decide` | #156 |
| F6 | Low | Raw exception text returned as HTTP error detail | The caller | #10 |

## Findings

### F1 — Founder brief readable through the Company Brain goal list

**What happens.** Founder project intake writes the whole brief, verbatim, into the goal description:

- `apps/backend/ago/company_chat.py:888` — `INSERT INTO ago_goals(id,tenant_id,created_by,title,description)` with `text` (the full brief) as the description.
- `apps/backend/ago/goals.py:66-73` — `list()` returns `id,parent_id,title,description,status` for **every** goal in the tenant.
- `apps/backend/ago/api_brain.py:58-65` — `GET /v1/brain/goals` checks only `brain:read`.

The project registry and project details apply per-project need-to-know (founder, accountable manager or activated stage assignee: `company_chat.py:1030-1100`). The goal list skips that check, so the brief leaks through a second door.

**Why "latent".** Out of the box only the founder gets `brain:read` (`bootstrap.py:45`); no setup script or migration grants it to others. But the repository's own test treats granting it to a reviewer as a supported configuration: `tests/test_company_project_delegation.py:93` (`test_confidential_registry_denies_unassigned_company_readers`) grants the reviewer `brain:read` and checks that `/projects`, `/projects/{id}` and `/delegations` are denied, but **does not check `/v1/brain/goals`**. In that exact scenario the reviewer can read the confidential brief.

**Fix proposal.** For intake-created goals, store a neutral description (for example the title plus `brief_digest`), and keep the brief only in `ago_founder_intakes`. Add a backfill migration for goals that already contain briefs. Extend the existing test to assert that `/v1/brain/goals` does not contain the brief text.

**Decision needed:** whether a backfill migration may rewrite existing `ago_goals.description` values on your local database.

### F2 — Agent-run results copied into readable evidence

- `apps/backend/ago/enterprise_store.py:2935-2977` — `measure_experiment` selects `a.result` from `ago_agent_runs` and saves `'source_outcomes': [dict(r) for r in rows]` into the evidence payload, so the full agent result is copied.
- `apps/backend/ago/enterprise_store.py:2113-2127` — `evidence()` returns `e.payload` in full.
- `apps/backend/ago/api_operations.py:1301-1313` — `GET /v1/operations/enterprise/evidence` checks only `operations:read`.
- `apps/backend/ago/provision.py:50` — the independent reviewer role is granted `operations:read`.

Elsewhere the code deliberately keeps agent results founder-only because they "can contain founder project excerpts" (`api_agents.py:63-67`, and the `CASE WHEN i.founder_id=...` in `company_chat.py`). This path undoes that.

**Fix proposal.** In `source_outcomes`, keep only the fields the metric needs (task id, status, review id, verdict, timestamps, the experiment digest and variant) plus a SHA-256 of the result. Never the result body. Add a test that a reviewer listing `experiment_measurement` evidence cannot see a planted result string.

### F3 — Raw financial documents in the evidence list

- `apps/backend/ago/enterprise_store.py:2979-2999` — `financial_document` stores the uploaded invoice or bank document as `content_base64` inside the evidence payload.
- The same list endpoint (F2) returns up to 100 payloads, including these bytes, to every `operations:read` holder.

The payload says it `requires_independent_document_review`, so some reviewer access is intended. Today, though, any `operations:read` holder gets the raw bytes in a bulk list, not just the assigned reviewer opening one document with an audit entry.

**Fix proposal.** Leave `content_base64` out of the list response. Serve it from a per-document endpoint that requires the review permission and writes an access audit row, the same pattern `document_vault.py` already uses.

**Decision needed:** which role may open a financial document, and whether you want that access audited.

### F4 — POSIX file modes do not protect files on Windows

AGO's owner runs it on Windows. On Windows, `os.chmod(path, 0o600)` only toggles the read-only flag and `mkdir(mode=0o700)` ignores the mode. Neither changes who can read the file.

- `apps/backend/ago/release_ops.py:119-144` — database backup and manifest (the backup contains the whole database, briefs included).
- `scripts/local_approved_agent_batch.py:41,50` — local dispatch receipts.
- `apps/backend/ago/database_store.py:278-308` — storage export directories.

Files under the user profile usually inherit a private ACL, so the risk is real mainly when a backup is written elsewhere (for example `D:\backups`, where other local accounts often have read access).

**Fix proposal.** On Windows, set an explicit owner-only ACL after creation (for example `icacls <path> /inheritance:r /grant:r "%USERNAME%:F"`), or refuse backup destinations outside the user profile, and print which protection was applied. Needs a Windows CI job or a manual check on your laptop, because Linux CI cannot prove it.

### F5 — Goal row embedded in integration proposals

- `apps/backend/ago/integration_store.py:888-899` — for `github_project` proposals, `_integration_source` stores `SELECT * FROM ago_goals ...`, which includes the description and therefore the brief.
- `apps/backend/ago/reviewed_changes.py:125-138` — `pending()` returns `p.*` (including `source`) to `approval:decide` holders.

A reviewer may need project context to approve, so this is low. **Fix proposal:** store `id`, `title`, `status` and a digest of the goal row instead of the full row. The tamper check at `integration_store.py:345` keeps working because it compares digests.

### F6 — Exception text as HTTP detail

- `apps/backend/ago/api_m2.py:185-192` — `translate_error` returns `str(exc)` for `PermissionError`, `LookupError` and `ValueError`.

I checked every `raise ...Error(f"...")` in `apps/backend/ago`: only 4 exist and none includes user or private data. The application's own messages are therefore static. Library `ValueError`s (for example `int()` parsing) can still echo caller input back to the caller. Low risk. **Fix proposal:** map known messages and return a generic detail otherwise.

## Checked and found clean

- **Tenant filter in SQL.** I parsed every string constant in `apps/backend/ago/*.py` and listed each `SELECT`/`UPDATE`/`DELETE` on an `ago_` table that does not mention `tenant_id`. There are 39 such statements, and all are expected: tenant-row locks, global token-hash lookups (MFA, identity tickets, SSO, OAuth codes, revoked sessions, integration credentials), the migrations table and the local tenant listing.
- **Security audit metadata** goes through the allowlist in `audit_redaction.py` (`security_controls.py:129`). Memory audits store a content SHA-256, not the content.
- **Event and message store.** `inspect()` returns no payload, and `last_error` takes only fixed categories (`message_store.py:105-117`).
- **Agent runs list** is founder-only (`api_agents.py:57-67`). Project details show the agent result only to the founder.
- **Document vault** (#134). The founder creates; a reader must be an active human, a current project member and hold the latest `grant` event. The list is filtered per document, and every read, list and denial is audited (`document_vault.py`).
- **Semantic memory search** is scoped through the reader's own visible rows (`semantic_memory_store.py:131-150`).
- **Backups** use exclusive creation, POSIX `0600`, are gitignored (`*.dump`, `*.backup`, `backups/`) and are blocked by `scripts/check_confidential_artifacts.py`.
- **Market watcher** fetches only allowlisted fixed URLs, sends no founder data and follows no redirects (`scripts/company_market_watch.py:35-40,200-211`).
- **Candidate export** refuses paths inside the repository and prints no brief, token or traceback (`scripts/ago_pull_candidate.py:130-173`).

## Not covered by this audit

- The web frontend (`apps/web`), apart from noting which components check `brain:read`.
- A line-by-line read of all 127 backend modules. I focused on routes that return reports, search results, evidence, documents, goals, memory, messages, tools and agent runs.
- Server access logs at runtime, Docker images and the PowerShell scripts beyond the candidate-export path.
- Runtime behaviour. Every finding above is from reading code and should be confirmed by a failing test before it is fixed.

## Proposed next step

One PR for Batch 1 that, for each of F1, F2, F3, F5 and F6, first adds a test that fails on today's code and then the fix, and leaves F4 for a Windows check. It needs:

1. Push access (Claude GitHub App installed on the repository).
2. Package access (`pypi.org`, `files.pythonhosted.org`, `registry.npmjs.org` allowed), so the tests can run before the PR.
3. Your answers to the two decisions above (F1 backfill, F3 access).
