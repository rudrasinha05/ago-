# AGO confidentiality: founder-owned documents and project registry

Status: reviewed local-development architecture decision (2026-10-21).
This document contains **no actual private project names, business briefs, credentials,
customer details, financial amounts, or confidential company portfolio**.

## 1. Where real information lives
**Authoritative source:** AGO's founder-controlled **local PostgreSQL**
(`ago_founder_intakes`, `ago_founder_project_lead`,
`ago_founder_intake_stages` and immutable approved delegation tables).
The founder decides when AGO and the laptop operate. No server or background
process is permitted to start on its own. An external Git host is not the AGO
database and is NOT a 24/7 execution service.

The software source repo (`rudrasinha05/ago-`) is **PUBLIC**. Do not put
the private master registry, strategic roadmap, invention descriptions, actual
customer records, salary, finance, credentials, or confidential project documents
in this repo, its Git history, wiki, commits, PRs, issues, CI logs or artifacts.

The master project list is a classified index and must stay in local AGO;
it is **not** a file to push to a GitHub repo shared with development workers.

## 2. Principal-centric authorization
Use access checks on every backend read, write and export. General
`organization:read` or `brain:read` alone are not need-to-know rights.

| Classification | Typical example | Authorized readers |
|---|---|---|
| Founder-only | Entire project registry, strategic opportunities, acquisition ideas, IP and finances | Authenticated, active human founder |
| Project-confidential | Detailed project brief, decision history, internal deliverables | Founder; accountable project manager; explicitly approved project-stage worker |
| Stage-limited | Implementation specifications, permitted task, review evidence | Only assigned stage worker and designated QA, further restricted by specific document ACL (not yet implemented) |
| Public-approved | Sanitized project description / marketing copy | Only after separate founder release approval |

For currently supported project registry, detailed brief and delegation history,
the backend restricts reads to the project's founder, its recorded accountable
manager, or an employee with an **activated, independently reviewed**
`ago_project_stage_delegation_activations` entry. Merely suggested employees,
another project's manager, and generic company readers are denied.
Employee identity, persisted role/tenant and authorization must be verified
on the server, never just concealed in the UI.

**Limit:** This is *project-scoped* access, not a finished per-document or
stage-specific ACL. A project-stage delegate could still view the entire
project brief. Do not put founder-only secrets into accessible project briefs
until a dedicated document ACL and field-level minimization layer exists.
Other API surfaces (global chat, activity, opportunities, reports, exports and
logs) need classification-by-path review before real confidential data is
entered. No claim of comprehensive secrecy before this audit.

## 3. GitHub: optional external versioned document storage

GitHub PRIVATE repos are reasonable for versioned *approved non-secret*
engineering design and documentation snapshots. They are not a replacement
for per-document AGO access. GitHub repository collaborators/teams generally
receive repository-scoped read access; do not rely on a directory tree or
`CODEOWNERS` to prevent a reader from seeing another folder's documents.

Suggested separation when founder *explicitly approves remote document storage*:

- **Local only:** master confidential project list, founder strategy,
  unreleased invention inventory, human/financial/customer information, keys.
- **One private repo per project:** sanitized docs and code for that project's
  approved collaborators, with independently verified repo visibility and
  collaborator/team permissions.
- **Founder-private administrative repo (optional, separate):** versioned
  *sanitized* policies/templates and change logs; no complete confidential
  project registry and no plaintext credentials.

If several projects need different readership, **do not combine them into one
private repository**. A private repo means inaccessible to strangers, not
automatically least privilege among its collaborators. For GitHub organizations,
configure base permission minimum and per-repo team read/write roles and
audit inherited team memberships. An ordinary personal account's collaborators
are coarser-grained.

GitHub integrations use reviewed, short-lived, per-repository credentials and
only an explicit permissioned action. AGO AI employee identity is *not* a GitHub
account. Never copy founder PATs into agent prompts, CI logs, docs, database
briefs, browser local storage, or worker-visible reports. GitHub keeps history:
removing a user does not retrieve previously cloned copies and deleting a
secret from the working tree does not erase historical commits.

**Do not create any new private GitHub repository, push a document or enable
remote synchronization solely because this policy file exists.**
This is a future explicitly founder-approved document-replication operation,
not cloud hosting of AGO workers.

## 4. Security acceptance before live confidential document upload

1. Audit all AGO endpoints that expose project title, brief, source signals,
   delegation, comments, task logs, reports, search, notifications or exports;
   add resource-scoped authorization and data minimization.
2. Add per-document ACL storage: document ID, exact project, classification,
   allowed employee identities/roles, expiry, review, denial audit, immutable
   revisions. Default deny, including for AI tools.
3. Complete negative PostgreSQL tests using an authenticated but unrelated
   company employee; independently test project owner, assigned staff, former
   staff, inactive users and a different tenant.
4. Verify cryptographically protected local database/backups, manual restore,
   safe archival/retention and access revocation behavior; do not assume
   GitHub private repos provide end-to-end encryption or automatic revocation
   of downloaded clones.
5. Before **each** optional GitHub sync, show the exact document set, source
   classification, recipient private repo ID, remote visibility, current
   collaborators/teams, and founder approval. Never sync automatically.

## 5. Founder operating rule
Laptop power, startup/shutdown, local watcher operation and local databases
remain entirely controlled by the founder. GitHub code CI may run for
explicitly pushed software changes; it does not authorize uploading company
secrets, public release or remote worker hosting. Never add Railway/cloud
hosting as a prerequisite for this local system.
