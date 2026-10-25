# AGO — AI Collaborator Work Board and Ownership Contract

**Applies to:** ChatGPT/JARVIS and Claude Code working on `rudrasinha05/ago-` **develop**.
**Authority:** Founder retains final scope/release decisions. This file coordinates assistant contributions; it does not grant AGO employees or coding assistants extra product authority.
**Scope:** Personal/local AGO; no implicit cloud, external publication, purchases or unattended machine startup.

## What each coding assistant must read before editing
1. `AGENTS.md` (for JARVIS/Codex) or `CLAUDE.md` (for Claude Code).
2. This file, `docs/PROJECT_HANDOVER.md`, `docs/architecture/SECTION_15_ROADMAP.md`, and the relevant architecture section.
3. [Open GitHub issues](https://github.com/rudrasinha05/ago-/issues), especially current scoped work issue and overall [#1](https://github.com/rudrasinha05/ago-/issues/1) / [#2](https://github.com/rudrasinha05/ago-/issues/2).
4. Actual `git status`, current `develop` HEAD, latest CI, and the task's changed files. Never trust a pasted or historical SHA as current.

## Permanent primary ownership (not permission grants)
| Area | Owner | Paths |
| --- | --- | --- |
| Core AI company, model inference, project orchestration, backend governance, memory, APIs | **JARVIS** | `apps/backend/ago/**` |
| Backend integration/regressions, PostgreSQL, SQL migrations, backend operator scripts | **JARVIS** | `apps/backend/tests/**`, `deploy/sql/**`, scoped `scripts/*.py` |
| Founder UI, 3D Brain, Company Map, projects, approvals, role/personnel visuals | **Claude** | `apps/web/**` |
| Frontend/browser-device/accessibility tests | **Claude** | `tests/frontend/**` |
| Shared contracts, root config, `.github/workflows/**`, full project acceptance, release coordination | **Joint review** | Edit one at a time only after GitHub issue handoff |

A path owner does not automatically own another system's behavior. In particular frontend cannot invent server operations/permissions or claim a model is running based on an animation; backend must not silently change UI contract.

## Current issues — source of truth for real task status
- **[Issue #3](https://github.com/rudrasinha05/ago-/issues/3) — CLAUDE / P0**, fix Section 6 WebKit crashes and browser navigation, preserve privacy checks. **Assigned, not started by evidence in this repository**.
- **[Issue #4](https://github.com/rudrasinha05/ago-/issues/4) — JARVIS / P1**, real governed CEO→CTO→PM→engineer backend delegation and evidence. **Queued, not started by this issue**.
- **[Issue #1](https://github.com/rudrasinha05/ago-/issues/1)** overall governed delivery; **[Issue #2](https://github.com/rudrasinha05/ago-/issues/2)** P0 authority/CI historical tracker. Neither is a complete overall-project acceptance denominator.
- For the **entire AGO project**, also track all original Phase −1–11, architecture Sections 1–34, M1–M12, UI/worker/GitHub delivery and owner-local acceptance. The 48-gate P0/P1/P2 ledger is a *subset*.

## Simple claim -> work -> handoff protocol
1. **Before starting:** Read the latest issue comments and branch, comment `CLAIMED by [JARVIS/Claude]; starting HEAD <sha>; touched paths ...; expected contract/blocks ...`. Only say `IN PROGRESS` when work actually starts.
2. **For a dependency:** Comment on the other collaborator's issue using `HANDOFF REQUEST: <specific API/data/behavior>`; record a realistic sample schema and exact tests; no direct edits to their owned paths until acknowledged. Claude cannot assume ChatGPT sees chat-only messages; JARVIS cannot assume Claude sees a ChatGPT conversation.
3. **Before committing:** Refresh remote branch, preserve unrelated changes, inspect exact diff and conflicts. Single shared `develop` branch per BDR; do not force push, rewrite history, create arbitrary branches or modify `main`.
4. **At each complete milestone:** Push one coherent, tested change; comment `HANDOFF READY: commit <40-character SHA>; files; tests PASS/FAIL; API contract; remaining work`. Update the task issue with verified status. For shared changes, request review before editing.
5. **Acceptance:** Both collaborators compare integration against one *same HEAD* CI run. Correctness requires real signed PostgreSQL/browser/worker tests where relevant, not solely compilation.
6. **Founder signoff:** Requires independently reviewable results for sensitive actions or project release. An AI assistant cannot attest to a human review it did not receive.

## Critical safety and quality
- No credentials/private founder briefs in GitHub issues, docs, test logs or prompts. Never grant repo write merely by changing this file.
- No fabricated AI runs, simulated business revenue, fake independent QA, AGO-origin GitHub commits or release status.
- Model/laptop/localhost execution requires actual founder-controlled machine and explicit local authorization.
- Do not skip tests or silence WebKit failures to manufacture green CI.
- Show `BLOCKED` truthfully for owner-side credentials, real device verification, or third-party human review.
- A green old commit does not make newer `develop` green.

## One-line founder dashboard convention
Report per workstream: **Owner | Current task issue | Actual status | Last commit | Last verified CI | Dependency | Next action**. Separate overall AGO architecture/delivery scope from the 48-item focused ledger.
