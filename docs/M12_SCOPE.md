# AGO M12 — Founder Local Operator Experience (frozen)

Approved by founder request to audit remaining phases, make AGO runnable and only
then conduct one consolidated local pull. This is a bounded implementation of the
**missing first-run operator module**, not permission to implement unsafe
unreviewed autonomous company functions or rewrite M1–M11.

1. A **read-only doctor CLI** checks local environment, PostgreSQL connection,
   exact migration checksums and signing-secret strength, without exposing
   credentials; no migration, SQL writes or network provider calls.
2. A **local-only interactive onboarding CLI** creates a new tenant, real
   founder and an *independent human reviewer*, with securely entered
   passwords; all-or-nothing DB transaction. It never changes preexisting
   tenant records or exposes a public HTTP signup endpoint.
3. A **one-command local launcher** starts AGO at localhost only after doctor
   passes, refuses production/staging mode and no configured database,
   and generates a non-persisted ephemeral **development-only** signing secret
   if absent (warn that a restart expires all sessions).
4. **Windows operator convenience**: short PowerShell entrypoint to run doctor,
   initialize, and serve from any working folder, without writing secrets or
   downloading/updating Python packages implicitly.
5. **Acceptance:** tests for redaction, no writes on failed doctor, duplicate
   setup rejection, atomic founder/reviewer signup and local-only serving;
   disposable PostgreSQL 16 CI, dual Python, Node, real Chromium and Docker
   gates remain green; documented launch/pull/safety guide.

BDR: modular-monolith first, single develop branch, no forced founder machine
changes; local setup requires the founder's own explicit execution. M12 does
NOT implement production invitations, OIDC/MFA, autonomous tool access,
marketplace, trained model agents, financial billing or a cloud host. Those
remain openly tracked as backlog with explicit acceptance criteria rather
than being invented as already complete.
