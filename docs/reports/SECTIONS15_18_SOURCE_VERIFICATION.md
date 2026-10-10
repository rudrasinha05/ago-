# AGO Sections 15, 17, 18 — Original Generated Blueprint Reconciliation

**Verification status:** ORIGINAL SOURCE RECOVERED AND COMPARED (documentation parity review). **Source:** founder-uploaded `ai-company-phase-minus-1-enterprise-architecture-blueprint.md`, dated 2026-06-30, 6,115 lines, SHA-256 `6589bc4f7e4f30287a61cefe3979b01d0b2a8357e3bb76dd6bb058d9e1daa1c4`.

The original was reviewed as **architecture-only Phase -1**; implementation code and SQL added in later AGO milestones do not retroactively redefine this blueprint. Never silently replace the original source with the separate V1 Phase 0–12 plan. The current development is personal/local and is not external production certification.

## Section 15 — Exact original 13-phase baseline (Phase −1 through Phase 11)
Source heading: `# 15. Implementation Roadmap`. Source contains goals, deliverables and testability criteria for **all 13 distinct phases**:

| Original phase | Exact original label | Original required exit evidence (summary) |
|---|---|---|
| −1 | Architecture Baseline | architecture review, threat model, dependency tests, ADR approval |
| 0 | Engineering Foundation | CI, local Compose/health, forbidden-import regression |
| 1 | Identity, Audit, and Messaging Foundation | auth/RBAC, immutable audit, transactional outbox/inbox, idempotent consumers |
| 2 | Organization and Employee Core | department, AI identities, skills, role, autonomy policies, dashboard |
| 3 | Workflow and Approval MVP | project/work item, workflow, assignments, approval gates, resume/cancel, audit |
| 4 | Memory MVP | governed retrieval, vector adapter, ingestion, provenance, memory dashboard |
| 5 | Execution Sandbox MVP | tool catalog, policy/quota, sandbox, credential leasing, artifact audit |
| 6 | Company Brain and Executive Council | strategy, policy, prioritized goals, voting/quorum, escalations |
| 7 | QA and Evaluation | evaluation plans, gates, findings, remediation and release QA |
| 8 | Communication Hub | internal channels, mentions, external-send approval, delivery audit |
| 9 | Simulation Lab | scenarios, experiments, digital twin projection, comparison, no live mutation |
| 10 | Production Hardening | observability, backup/restore, threat model, load, DR and SLO proof |
| 11 | Microservice Extraction Readiness | optional extraction eligibility and before/after contract equivalence |

**Detected divergence:** Current `docs/architecture/SECTION_15_ROADMAP.md` maps a *different, separately recovered Phase 0–12* roadmap (Platform Core → Organization OS → ... → Research). This is not the same authored Phase −1–11 roadmap; neither has been erased or substituted. **Resolution:** Preserve both as distinct historical versions; this file is the canonical crosswalk for the original generated blueprint. The local milestone M1–M12 numbering is also separate. No claim is made that future optional production, Kafka/Kubernetes or microservice extraction are currently deployed.

## Section 17 — All eight exact original non-goals
Source heading `# 17. Non-Goals for Phase -1`.

1. No production code.
2. No database tables.
3. No final LLM prompt design.
4. No final model/provider commitment.
5. No UI visual design system implementation.
6. No final deployment topology.
7. No customer-specific compliance certification.
8. No microservice extraction.

Current `SECTION_17_PHASE_MINUS_ONE_NON_GOALS.md` has a stronger explanatory exclusion narrative; it is consistent with but does not enumerate the exact original eight as a checklist. The original list above is an explicitly preserved source crosswalk. All eight refer **only to Phase −1**.

## Section 18 — Original ten canonical technology references
Source heading `# 18. Reference Technology Sources`.

| Canonical topic | Original URL |
|---|---|
| FastAPI | https://fastapi.tiangolo.com/ |
| Next.js | https://nextjs.org/docs |
| PostgreSQL | https://www.postgresql.org/docs/ |
| Docker Compose | https://docs.docker.com/compose/ |
| Kubernetes | https://kubernetes.io/docs/ |
| Apache Kafka | https://kafka.apache.org/documentation/ |
| Temporal | https://docs.temporal.io/ |
| OpenTelemetry | https://opentelemetry.io/docs/ |
| HashiCorp Vault | https://developer.hashicorp.com/vault/docs |
| Qdrant | https://qdrant.tech/documentation/ |

The current `SECTION_18_REFERENCES.md` provides an expanded selected/local/deferred source matrix. Missing explicit baseline items in its main table must **not** be interpreted as removed from the original blueprint; the ten URLs remain normative *historical references*, not technology-installation commitments. No original-version pins or certification claims were supplied.

## Disposition
- Original artifact has now been recovered and exact sections compared to the current authored documentation, with divergences disclosed and linked above.
- **Source verification: CLOSED. Exact verbatim document identity with modified/extended current documentation: NOT CLAIMED.**
- Original 13-phase baseline, eight non-goals and ten references are explicitly preserved here without revising original manuscript.
- Source SHA and an evidence table now permit a separate independent reviewer to verify against the founder's unmodified upload.
- Any master checklist update needs owner approval to replace the older source-blocked text; unrelated acceptance gates remain independent.
