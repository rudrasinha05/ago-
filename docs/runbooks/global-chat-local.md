# AGO Global Chat — Founder local acceptance (P0)

AGO does not treat an AI reply, a governed task, its QA verdict, and a
production release as the same thing. Only persisted evidence permits a
respective status. Founder authority remains final on spending, risky
operations and deployments. Local Ollama does not require a new paid API.

## Workflow

- Every Founder Global Chat message, including messages without tags, is
  recorded with a system-labelled receipt. The active appointed CEO owns the
  default response. Tagging by unique employee UUID or employee name creates
  additional accountable pending work items.
- Human acknowledgment requires the addressed human's signed reply. AI
  acknowledgment requires a recorded actual local-model response.
- A CEO handling an untagged Founder order may recommend exactly one active AI
  direct report; the backend verifies reporting hierarchy before recording a
  pending assignment. This does not approve or execute tasks.
- Task status and independent QA come from actual governed task/review records,
  not from chat text or an AI response.
- Unknown tags, cross-tenant IDs, terminated staff and stale model claims
  fail closed. A missing active CEO keeps the Founder order blocked.

## Install / verify only AFTER reviewed PR merge and passing CI

1. Let the active AGO task finish and back up the existing Founder PostgreSQL
   data. Keep the local 'Claude outputs/' master-checklist folder intact.
2. Fast-forward the existing develop checkout without reset, stash or clean.
3. Apply the reviewed AGO migration 078 using the normal tested migration
   process. Do not run destructive SQL or create a second organization.
4. Restart AGO using the existing local launcher, then sign in again. The
   development signing key may rotate on restart.
5. Send a Founder question in Organization & Chat without tagging: the
   appointed CEO should be accountable.
6. Send an explicit Founder order tagging one eligible employee; inspect
   saved recipient status, real AI/human acknowledgment, linked task and QA.
7. Disable local Ollama and verify the order stays pending without a
   fabricated reply or approved task.
8. Independently verify any generated code and release via the existing
   Docker QA and governed delivery gates.

## Optional Founder-started browser-independent reply worker

Read-only preview (asks for organization UUID, Founder email and password,
the latter hidden from terminal echo):

    cd "C:\Users\rudra\Projects\ago-"
    python .\scripts\ago_global_chat_runner.py

Explicitly process pending local AI replies, bounded to four hours / 100
model responses:

    python .\scripts\ago_global_chat_runner.py --apply --confirm PROCESS_PENDING_GLOBAL_CHAT_AI_REPLIES --hours 4 --max-replies 100 --interval-seconds 20

The worker never starts at boot or contacts an external server. It does not
save the Founder password or bearer on disk, and it never auto-relogs in
after 401/revocation. A still-authorized bearer is rotated every ten minutes;
the absolute interactive session age remains enforced by AGO.

A processed reply queue is reported as 'queue_acknowledged_not_executed',
NOT 'project_done'. Project execution is still handled by the governed
project runner and independent QA.

## Blockers and recovery

- No appointed CEO: Founder must appoint a verified AI CEO.
- Ollama disabled/unreachable: order remains pending; no paid fallback.
- Another in-flight model call: a fenced claim prevents duplicate inference.
- Three exhausted attempts: Founder reviews and explicitly retries via a new
  follow-up; no infinite automatic retry.
- Revoked/expired Founder session: stop; user starts a new authenticated session.
- QA fail or absent evidence: never automatically claim PASS or release.
