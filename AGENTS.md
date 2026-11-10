# AGO — JARVIS / coding agent instructions

Project `rudrasinha05/ago-`, implementation branch `develop`. Read **[docs/AI_COLLABORATION.md](docs/AI_COLLABORATION.md)** before starting. Cross-assistant coordination is through GitHub issues/comments/commits/CI, **not** presumed live ChatGPT-to-Claude communication.

Primary coding ownership: `apps/backend/ago/**`, `apps/backend/tests/**`, `deploy/sql/**`, related backend scripts. Core AI Company: real governed Ollama chain, CEO→CTO→PM→engineer handoffs, runtime/recovery, bounded tool and model execution, safe engineering/test/repair, AGO-origin approved GitHub handoff and real acceptance gates.

Current issue [#4](https://github.com/rudrasinha05/ago-/issues/4) is a **P1 queued task**, not already executed. Claude owns `apps/web/**` and `tests/frontend/**` and [Issue #3](https://github.com/rudrasinha05/ago-/issues/3) P0 WebKit work. Never edit its files or shared CI/contracts without GitHub handoff.

Preserve original full AGO phases/34 sections and owner personal/local-only scope. The 48-task acceptance ledger is **not** the entire project. Founder approves final consequential actions. Never manufacture QA, real model/laptop evidence, external provider access or release; keep independent review, tenant isolation, and accurate same-head CI.

Before any change: check actual head and scoped issue, claim if starting, inspect concurrent writes. No forced push or `main` change. Upon completion: post commit SHA, tests, failure cases, API handoff and accurate status to GitHub issue.


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

