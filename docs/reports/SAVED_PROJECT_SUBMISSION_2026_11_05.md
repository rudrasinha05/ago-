# Saved project submission — 2026-11-05

Persisted draft projects could be inspected after returning to the workspace, but
only the transient newly-created project card exposed submission for approval.
The selected saved draft now exposes an explicit submit action when it has a plan
step. Successful submission updates the matching detail and portfolio; failed
submission keeps an explicit retry. A late response cannot overwrite another
selected project's detail. Approval and execution remain separate actions.

The implementation preserves develop's real-Founder permission fix: the delivery
journey uses stored read permissions and the Founder role, without requiring the
server-derived `approval:founder` permission in `/me`.

Validation added:
- Browser fixture regression: no submit on inspection, visible failure, explicit
  retry, and pending-approval state after success.
- Real signed-session/PostgreSQL Next.js regression: actual `/me` permissions,
  persisted draft creation, journey inspection, submission, database approval
  state, zero agent runs, and persistence after signing in again.

Local SDK tests, production Next.js build, targeted Chromium regression, Ruff,
frontend architecture, engineering quality, and diff whitespace checks passed.
The initial browser attempt preceded the Chromium download and could not launch;
the rerun passed after installation. Real PostgreSQL/browser execution is delegated
to the repository CI; this report does not predeclare its outcome.

No API, migration, permission grant, automatic approval, or automatic execution was
introduced. This bounded fix does not complete owner-device/Ollama verification or
the full source-export → Docker QA → independent human review → GitHub journey.
