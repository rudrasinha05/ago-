# Section 9 — Frozen Memory Architecture

Scope is the seven supplied checklist gates, within the founder-authorized
Sections 8–10 batch. Section 8 must pass before implementation begins.
The unavailable original blueprint is not reconstructed or silently substituted.

| Gate | Required evidence |
| --- | --- |
| Employee/department/project/company | Private employee ownership; current department membership; explicit goal-backed project membership; same-tenant company sharing; no founder private-memory bypass |
| Experience/episodic/short term | Typed episodic and working records; bounded expiry (working at most 24 hours, episodic at most 365 days); expiration excludes records before cleanup |
| Authorized persistence | Caller-owned transaction, live database grants, same-tenant foreign keys, strict HTTP DTOs; unauthorized and cross-scope denial |
| Vector semantic retrieval | Reuse actual offline Section 7 ONNX encoder; model fingerprint and 384-dimensional normalized vectors; scope/expiry predicates before ranking; real paraphrase relevance test |
| Consolidation/summary/forgetting | Deterministic extractive consolidation with explicit source IDs and same scope, no authority promotion; correction invalidates indexes/derived summaries; deletion scrubs content/vectors and derived summaries |
| Audited evidence/graph | Source reference, actor, digest, immutable metadata audit; optional same-tenant verified knowledge-node link; private content is never published into the shared graph |
| Retention/privacy/provenance/correction | Explicit expiry, revision and optimistic correction conflict checks; no stale vectors; source correction/forget invalidates descendants; audited bounded expiry cleanup |

New memory tables are additive; existing `/v1/memory` behavior remains compatible.
New routes are under `/v1/knowledge/memory`. Project means an explicitly enrolled
AGO goal workspace, not an invented external project service. Membership is
managed by an authorized human and checked live. Memory is unverified experience;
a link to reviewed knowledge does not turn remembered claims into approved facts.
Summaries are short verbatim excerpts with recorded provenance, not LLM output.
No external API/model/service is required. Production acceptance of Section 10
remains separate from these bounded internal implementation gates.
