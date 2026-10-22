# AGO P1: First real, recorded employee execution

## Current verified scope
A founder-only panel inside Company Map → Execution Desk enables a **separate, founder-initiated** task creation for an existing AI employee using the authorized `POST /v1/tasks` route. The founder chooses either `internal:brief` (deterministic smoke test; no LLM) or `research:brief` (configured model runtime + virtual credits required). After a server-confirmed `proposed` task, the existing Execution Desk handles Request approval → independently authorized human decision → Run approved AI; Governance separately handles QA. UI does not self-approve, create fake AI employees, associate an arbitrary new task with a confidential founder project, call GitHub, publish software, or claim a real Ollama run without model activation.

## Founder local verification

1. Start AGO normally and sign in to `/workspace/organization/`.
2. Roles & Expertise: inspect actual specialist records; ensure at least one AI employee exists.
3. Execution Desk → First AI employee run → choose recorded AI employee and action → Create proposed task.
4. In the task register choose Request approval. In Founder Approvals choose explicit review with a reason. In a multi-human tenant a different authorized reviewer must approve; founder solo mode requires opt-in and actual sole-human eligibility.
5. When status becomes approved, choose Run approved AI. Review durable result; finish with Governance → Pending QA by an authorized independent human.

For real local model text (not deterministic smoke), start Ollama yourself and verify it with `./scripts/ago-ollama-check.ps1 -Model qwen2.5-coder:1.5b`. Before launching AGO in the same terminal, explicitly set `$env:AGO_LLM_PROVIDER='ollama_local'`, `$env:AGO_ENABLE_LOCAL_MODELS='true'` and `$env:AGO_LLM_MODEL='qwen2.5-coder:1.5b'`; the installed model must match and the virtual credit budget must allow at least one attempt. This enables the `research:brief` opt-in handler, **not** a four-person company workflow. It does not grant tools or bypass QA. The separate `scripts/local_approved_agent_batch.py` still processes **only internal:brief** tasks, so do not use that batch to test research:brief.
