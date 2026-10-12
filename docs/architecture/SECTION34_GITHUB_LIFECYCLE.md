# Governed GitHub project lifecycle

Agreed owner: `rudrasinha05`. Each independent AGO project binds to one private
repository; tasks for an existing project reuse that binding. `develop` is the
working branch. `main` is reserved for stable owner-approved releases.

The CEO creates a goal and approves the project roadmap, AI PM, developers and an
independent QA identity in Operations & Tools → GitHub project. The exact package
then receives an independent human Governance review. Applying the package records
the immutable project/repository binding; it does not create a remote repository.

GitHub operation proposes an exact change: create or link a private repository,
initialize `develop` from an explicitly reviewed default-branch SHA, create/update
an issue, commit reviewed UTF-8 files to an expected `develop` SHA, or open a draft
`develop` → `main` PR. Commits cover development, fixes, tests, workflows and docs.
An independent review and application precede explicit dispatch. An active founder
currently dispatches on behalf of the accountable PM; AI PMs cannot acquire CEO
credentials or independently authorize GitHub mutations. Draft PR review/merge is
a separate owner action. Deletion, transfer and permission changes are unavailable.

Use the original project ID for every subsequent task/operation. Repository
binding cannot be renamed or reassigned through this API. QA identity cannot equal
the PM or a developer. Current human reviewer authority and unchanged project
configuration are checked again at dispatch. Version-control updates are non-force;
a stale expected SHA fails rather than overwriting others' commits.

## Local configuration

Set `AGO_GITHUB_ENABLED=true`, `AGO_GITHUB_TENANT_ID=<authorized organization UUID>`
and `AGO_GITHUB_TOKEN` in the backend's secret environment. Never put the credential
in a proposal, repository file, browser storage or report. The token must be
owner-authorized for the specific selected private repos and operations. Creating
a personal repository additionally needs a credential that supports `POST /user/repos`;
an installation token restricted to existing repos cannot be assumed to do this.
The service verifies the authenticated personal owner before repository creation.
A ChatGPT GitHub connection is not automatically an AGO backend credential.

## Recovery and verification

The service durably records `started` before network I/O and `succeeded` afterward.
A network failure/crash can leave an uncertain operation even when GitHub accepted
it. Repeat dispatch is blocked, not blindly retried. Search the repository/issue/PR
body or commit message for `ago-operation:<operation UUID>`, compare exact remote
state and approve a replacement only when remote reconciliation establishes it
is needed. Status reports include the current `develop` SHA and the workflow runs
for that same SHA, with pagination truncation made explicit. Green CI is not itself
QA approval, owner release approval or proof of connector credentials being installed.

Tests exercise real PostgreSQL approvals/dispatch receipts with a recorded fake
transport; provider-contract tests inspect the actual outgoing REST method/path/body.
They do not claim that a live customer GitHub credential or new private repo was tested.

Primary API references: https://docs.github.com/en/rest/repos/repos,
https://docs.github.com/en/rest/git/refs,
https://docs.github.com/en/rest/git/trees,
https://docs.github.com/en/rest/git/commits,
https://docs.github.com/en/rest/pulls/pulls.
