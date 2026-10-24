# Section 18: verified primary engineering references

Retrieved 2026-10-10 using official primary documentation. These references inform specific selected/local or deferred decisions; consulting a source does not deploy a product or upgrade dependencies. Full original generated bibliography is unavailable and exact bibliography fidelity remains unverified.

| Primary source | Version/date reference | AGO rationale and adoption boundary |
|---|---|---|
| [FastAPI larger applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/) and [dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/) | Live docs, retrieved above; backend range in pyproject.toml | Router composition, strict DTOs and scoped injection; no wholesale framework migration |
| [Next.js static exports](https://nextjs.org/docs/app/guides/static-exports) | Live App Router docs; exact Next version in package-lock.json | Actual exported eight-workspace UI bundled with Python, no Node deployment |
| [PostgreSQL16 transactions](https://www.postgresql.org/docs/16/sql-set-transaction.html) | Version16 docs | Statement/transaction consistency and additive schema controls; operational metrics collected in one SQL statement |
| [Docker Compose](https://docs.docker.com/compose/) and [production patterns](https://docs.docker.com/compose/how-tos/production/) | Live docs | Non-root loopback preview and explicit restore; production patterns are reference only |
| [Redis documentation](https://redis.io/docs/latest/) | Live docs; Python client6.4.0, CI server7.4 | Optional scoped traversal cache, authoritative state remains PostgreSQL |
| [FastEmbed](https://qdrant.github.io/fastembed/) | Live project docs; package0.7.4 | Existing pinned real local embeddings, tested dimensions/digest/recovery |
| [Ruff configuration](https://docs.astral.sh/ruff/configuration/) | Live docs; constrained <1 in dev dependencies | Selected stable lint baseline, not an invented formatting guarantee |
| [pytest](https://docs.pytest.org/en/stable/) | Live docs; >=8,<10 project range | Unit and actual PostgreSQL tests with explicit fixture isolation |
| [Coverage.py](https://coverage.readthedocs.io/en/latest/) | Retrieved documentation7.16.2; pytest-cov>=7,<8 | Statement execution floors across modules, not proof of correctness |
| [Semantic Versioning2.0.0](https://semver.org/) | Stable specification2.0.0 | Future release increments and explicit compatibility review |
| [RFC9457](https://www.rfc-editor.org/rfc/rfc9457) | Published2023, retrieved above | Error interoperability reference; AGO retains current correlated envelope and does not claim RFC9457 conformance |
| [OpenTelemetry observability primer](https://opentelemetry.io/docs/concepts/observability-primer/) | Live docs | Metrics/logs/traces vocabulary; collector/hosted aggregation deferred for personal use |
| [OAuth2.0 Security BCP, RFC9700](https://datatracker.ietf.org/doc/html/rfc9700) | January2025 specification; retrieved2026-10-10 | Authorization-code/PKCE, redirect and token threat-model reference; no claim of universal certification |
| [Authenticated encryption, Cryptography](https://cryptography.io/en/latest/hazmat/primitives/aead/) | Live docs labeled51.0.0-dev1 at retrieval; installed project range46–48 remains authoritative | Existing authenticated-encryption/MFA adapter rationale; reading newer docs does not upgrade dependency |
| [RabbitMQ reliability guide](https://www.rabbitmq.com/docs/reliability) | Live docs retrieved2026-10-10; product is not installed by this batch | Acknowledgement/retry/reliability comparison for ADR004 broker alternative; AGO retains PostgreSQL outbox/inbox |

Security/distributed alternatives: OAuth/OIDC verification and encrypted MFA already have tested Section10 adapter contracts. This bibliography does not replace their recorded security evidence or external review. ADRs list RabbitMQ/Kafka, Temporal/Camunda, Neo4j/Qdrant and cloud stores as alternatives; no version or installation is asserted for unadopted products. Version authority is pyproject.toml for backend ranges, package-lock.json for npm exact resolution, deployment image tags for CI services and actual model manifest for embedding identity. Recheck primary docs and complete the full matrix before any upgrade.

Do not use vendor marketing or generated summaries as authority for comparative performance, security certification or financial ROI. Future Phase12 comparisons require pinned environments, reproducible input/evaluation, raw results and stated uncertainty.


## Original ten canonical links, preserved verbatim (P0 #18)

Source: the founder-uploaded original generated blueprint, SHA-256
`6589bc4f7e4f30287a61cefe3979b01d0b2a8357e3bb76dd6bb058d9e1daa1c4`.
The original list is historical **reference material**, not a mandate to
install every product on the founder's Windows laptop.

| Original technology | Exact original reference | AGO disposition |
|---|---|---|
| FastAPI | https://fastapi.tiangolo.com/ | Adopted locally |
| Next.js | https://nextjs.org/docs | Adopted locally |
| PostgreSQL | https://www.postgresql.org/docs/ | Adopted locally |
| Docker Compose | https://docs.docker.com/compose/ | Adopted for local preview/test |
| Kubernetes | https://kubernetes.io/docs/ | Deferred; no production cluster |
| Apache Kafka | https://kafka.apache.org/documentation/ | Deferred; PostgreSQL durable outbox selected |
| Temporal | https://docs.temporal.io/ | Deferred; local task scheduler and durable journal selected |
| OpenTelemetry | https://opentelemetry.io/docs/ | Documentation reference; no hosted collector claimed |
| HashiCorp Vault | https://developer.hashicorp.com/vault/docs | Production/optional vault deferred; local protected secrets only |
| Qdrant | https://qdrant.tech/documentation/ | Local vector index/embedding alternative selected, no Qdrant server claimed |

Compare the recovered canonical list and later curated engineering links
using `scripts/check_p0_original_parity.py`. No undocumented technology
adoption or external certification is implied.
