# Section 16: architecture authority and change control

Founder sets personal-use scope and authorizes engineering work. JARVIS implements and verifies technical changes. A distinct authorized human decides consequential runtime approvals; proposer cannot approve their own change. Council advice does not substitute for human authority. Existing immutable approval/audit records remain the decision authority. Actual GitHub branch protection is an external unverified setting, not implied by CODEOWNERS or CI.

Baseline: versioned exact dependency policy, module inventory, repository ports/SQL contracts, OpenAPI contract, ADR index and scope document. Record SHA-256 baseline/candidate digests, affected sections, rationale, cross-context impact, rollback and evidence reference before proposing an architecture replacement. Changes affecting constitutional Section29 are rejected by this ordinary route and require a separately defined higher authority; this batch does not implement constitutional amendments.

Runtime API: POST /v1/meta/architecture/changes requires brain:manage; GET requires approval:read; POST /{id}/reconcile requires brain:manage. Proposal creates an exact architecture:review:<id> approval and immutable tenant-scoped change record. Another authorized human decides via existing Governance. Reconcile records accepted/rejected; pending, self approval, foreign tenant and repeat finalization fail. Accepted means the decision is recorded, not that a repository, process, database or cloud resource was changed. Applied is always false.

Threshold: every submitted architecture proposal needs one independently authorized human approval. No low-risk route is exempt from this submitted-proposal rule. Larger production, database replacement or constitutional changes additionally require founder scope acceptance and separately applicable authority; they cannot gain broader rights through this endpoint.

ADR amendment: retain prior file/ID; add a successor with supersedes link, classify compatibility and provide reviewed migration/rollback evidence. Rejected proposals remain immutable history. Descriptive evidence references and digests are review claims, not fabricated proof of deployment. Human reviewer checks the actual corresponding artifact.

Exceptions: preserve Section14's precise source/target/reason/change request/author/distinct reviewer/review date/expiry fields. No cycle/dynamic unknown import waiver; expired or malformed exceptions fail. Update contract and inventory only after actual accepted scope change. CI rejects unregistered import edges and unauthorized SQL writers.

Audit: every push/PR runs the existing source/diagram/layer/frontend checks plus the engineering gate. A scheduled weekly GitHub workflow_dispatch-capable read-only audit runs the same checks against develop; it never changes files, submits approvals, deploys or contacts others. Runtime executive snapshots independently record the packaged static dependency audit and policy digest. Scheduled audit requires GitHub Actions enabled and is not silently installed on the owner's laptop.

Compatibility review and negative tests: current public request/response schema manifest plus real sessions/PostgreSQL immutable approval checks. Periodic static audit complements actual runtime tenant/permission checks; it is not an external security certification.
