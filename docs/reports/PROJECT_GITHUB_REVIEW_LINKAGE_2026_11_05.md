# Project-linked GitHub review

The Founder delivery overview omitted pending GitHub operations because its
approval source only linked strategic plans and tasks. A pending independent
GitHub decision now links through the exact integration proposal, latest enabled
GitHub binding and matching Founder intake goal, all in the same tenant.

The proposal must match the approval ID, requester and full action/digest. Only
identifiers are projected; source files, proposal payloads and private briefs are
not copied into the overview. GitHub operation reviews stay independent: the new
link is deliberately separate from `founder_intake_id`, which drives strategic
Founder authority. Disabled latest bindings cannot revive an older enabled one.
The approval UI labels this review explicitly.

The CompanyChat read contract adds two existing tables: enterprise proposals and
integration settings. No protected writer, dependency, endpoint or migration is
changed. No GitHub/provider call or write occurs when reading the journey.

Regression coverage includes exact project matching, unrelated/decided reviews,
disabled bindings, another tenant, self-approval denial, private source omission
and zero GitHub dispatches during the whole read/review scenario. Actual database
acceptance runs in the existing PostgreSQL CI; local database skips are not passes.

Remaining product work is explicit: private Docker test receipts currently live
in local files, not a server-verifiable delivery record. The overview's Docker,
GitHub and release flags are not upgraded from approval existence. A complete
source-bound pipeline, actual owner Ollama/Docker run, independent artifact review
and AGO-origin provider receipts are still required for full product acceptance.
