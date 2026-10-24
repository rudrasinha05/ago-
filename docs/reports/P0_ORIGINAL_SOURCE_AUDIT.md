# P0 original architecture crosswalk — honest implementation parity

The source-of-truth record for the original **Phase −1 through Phase 11**
roadmap, **eight** Phase −1 non-goals and **ten** original technology
references is `SECTIONS15_18_SOURCE_VERIFICATION.md`. That previously
recorded founder-uploaded blueprint was 6,115 lines long with SHA-256
`6589bc4f7e4f30287a61cefe3979b01d0b2a8357e3bb76dd6bb058d9e1daa1c4`.
This checkout has the recorded comparison, **not** the original plaintext
blueprint bytes. Consequently this CI gate does not claim to rehash the
original upload; it verifies the exact *already recovered* original version
against version-controlled documentation and refuses silent replacements.

Original architecture Phase −1–11 and later Phase 0–12 are **different
documents** with distinct milestones. Both stay preserved. Phase −1
excluded production code, DB schemas, final provider/prompts, UI system
implementation, deployment topology, certification and microservice
extraction. Later implementation code **does not** retroactively invalidate
those Phase −1 exclusions. Original Kubernetes, Kafka, Temporal, Vault
and Qdrant references are **not claims that those services are running**.

### All 34 sections source register

`P0_34_SECTION_SOURCE_PARITY.json` is an exact 34-row source register with
one architecture record, one existing implementation/source pointer and a
non-synthetic status per section. Run
`python scripts/check_p0_original_parity.py` to reject a missing
section, altered source pointer, dropped original baseline and blanket
"all implemented" assertion.

**Important:** a file pointer and historical section-specific scoped CI are
not proof of a fully autonomous AI company. Sections 11–13, 16,
19–27 and 34 retain substantial operational gaps; 25 is still
design-only in the scoped marketplace sense. Even where earlier sections
passed bounded CI, the founder's actual machine, external integrations,
genuine cross-project QA and production attestations are NOT implied.
Original item #36 stays Partial until its original end-to-end requirements
are met and independently verified.

### Scope and outstanding acceptance

- #15 / #17 / #18 have historical recovered-source comparison and these new
  machine guards; they may be judged complete as **documentation parity**
  only after latest full acceptance CI and explicit register review.
- #36 documents all 34 source mappings while identifying unimplemented
  original behavior. Mapping does not itself complete #36.
- #10 / #133 / #134 / #156 require signed API, reports, logs, search,
  tool/export and backup evidence; source-only assertions are insufficient.
- #158 requires the final **same SHA** nine-job architecture, browser,
  complete backend and focused suite all green, with no silently reused
  earlier-green commit.
