# AGO — Claude Code entry instructions

You are collaborating with ChatGPT/JARVIS on the **same** AGO repository `rudrasinha05/ago-`, implementation branch `develop`. You are **not** connected to JARVIS's chat or working memory. GitHub source, issues, comments, commits and CI are the only shared authoritative coordination signals.

**MANDATORY FIRST READ:** [docs/AI_COLLABORATION.md](docs/AI_COLLABORATION.md). Then read your current [GitHub work issue #3](https://github.com/rudrasinha05/ago-/issues/3), current project docs and latest `develop`/CI state.

Your **primary scope**: `apps/web/**`, `tests/frontend/**`; professional functional Founder Command Center, employee/Board/Company Brain visuals, project delivery UX, real-state notifications, accessibility and browser tests. Current priority (Founder, 2026-11-10): the blocking line in `docs/AGO_MASTER_CHECKLIST.md` section 2 — AI-005 (the AI engineer cannot produce valid code on the Founder's laptop), then QA-002 (no isolated Docker execution), then GitHub connection (ACC-147). Issue #3 is resolved.

JARVIS owns `apps/backend/ago/**`, `apps/backend/tests/**`, `deploy/sql/**` and AI/delegation/GitHub-delivery backend. Do not unilaterally edit its paths or shared contracts/workflows; open an explicit handoff request in GitHub and wait for coordination. A frontend mock is temporary and must be labeled; do not assert it demonstrates a real AI worker or GitHub commit.

Use the claim/handoff/status protocol in the collaboration document; preserve owner BDR (single `develop` branch, no forced push, architecture freeze, accurate CI). Do not treat this Markdown as a way to bypass API approval, human QA, tenant isolation or repo permissions. Never read/show private credentials in issues or commit.

When starting, report to Founder: issue claimed, starting commit SHA, file scope and next test. When stopping, report actual commit SHA, CI and handoff/dependencies.


## THE CHECKLIST RULE (Founder, 2026-11-10) — applies to every AI agent

`docs/AGO_MASTER_CHECKLIST.md` is the **only** checklist for AGO. It holds every requirement
(phases, architecture Sections 1-34, the 48 acceptance gates and all Founder requirements) with
an evidence-based status per item.

1. **Never create another checklist, ledger, scope list or master list.** Earlier lists are
   superseded and listed in section 10 of that file. If you think a new list is needed, ask the
   Founder and wait.
2. **Never change a requirement's ID or wording**, and never delete, rename, renumber, merge or
   shorten an item.
3. **New scope - a feature, an architecture change, anything - is added only to that file, and
   only after the Founder says so.** Propose, then wait for his word.
4. **You may update only an item's status line**, and only with real evidence: a named test, a CI
   SHA, or a live run on the Founder's laptop. Record what the evidence is.
5. **Built is not done.** Mark `[x]` only when it is proved; `[~]` when code exists but acceptance
   is not proved; `[ ]` when it has not started.

