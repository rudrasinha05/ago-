# Founder delivery journey integration — 1 November 2026

Implementation continues the Founder's frontend/backend request on develop,
starting at 4d7fe1dada8ff12c2fe1a27f6b44a98d2e1c7315. Existing issue #7's
read-only delivery-overview API is now connected to the Command Center. This
is an implemented navigation/progress workflow, not autonomous release.

## Delivered behavior

- Founder Command Center shows persisted project progress, responsible manager,
  stage workers, QA state, failures and guidance for the actual delivery state.
- Start a project opens the existing intake. Inspect project opens the exact
  selected project, including projects outside the first portfolio page. There
  is no UUID entry in this path.
- View project work opens the existing governed Execution Desk filtered to the
  exact task IDs returned by the signed project overview. The desk refreshes
  actual activity; Show all company work restores the full queue. Task requests
  and model dispatch retain their original explicit actions and server checks.
- Linked pending requests lead to the existing approval inbox. Independent QA
  and GitHub evidence use the existing review screens; no automatic approval,
  model execution, Docker run, GitHub write or release occurs on navigation.
- Projects paginate in groups of 20. Overview refresh is read-only and runs
  while its Command Center tab is active. Failed/malformed responses clear the
  previous summary instead of leaving stale successful evidence on display.
- Every read permission and Founder role is required before overview polling.
  Late responses are ignored on navigation, refresh or changed selection.
- Fixed a pre-existing portfolio selection race: an older project-details
  response or CEO-refresh response cannot overwrite the newly selected project.

## Contract and boundaries

The existing overview now includes stage task_id (string or null), projected
from the same authorized project record. No new endpoint, permission, model,
SQL migration, external provider or session storage was added. Existing API
fingerprints and module boundaries remain unchanged. Pure frontend state
checks reject missing/unknown overview shapes and do not equate completed
execution with passed QA or release. The approval count is explicitly labelled
as linked requests in the current inbox, not a guaranteed total across all
historical approvals. GitHub verification is separate, not inferred from stage QA.

## Verification

- Local full backend: 1044 passed, 252 PostgreSQL-dependent skips; one upstream
  Starlette deprecation warning. Skips are not counted as integration passes.
- SDK and new projection checks: 46 passed. UI compatibility: 20 passed.
- Next.js web build and canonical static packaging passed.
- Four new Chromium browser regressions passed: exact project selection and
  scoped tasks with no writes; pagination/XSS-safe text/malformed evidence and
  recovery; permission-gated reads; delayed project-details race.
- The journey is included in the existing WCAG AA browser check. Existing
  multi-browser, signed PostgreSQL and independent-human CI gates remain enabled.
- Architecture, SQL boundaries, privacy, API compatibility and lint checked.

## Explicit remaining work

This closes the unused delivery-overview API and fragmented progress-navigation
slice. It does not yet turn private source export, local Docker QA, human
review and prepared GitHub submission into one automated browser operation.
Those capabilities require their existing exact-source evidence and explicit
approvals. Owner Windows/Ollama/device acceptance remains unverified here.
No full-project or production release completion is claimed.
