# Section 17: Phase −1 non-goals and phase separation

Phase −1 means design before implementation. Its deliverables are architecture boundaries, responsibility/contract maps, component diagrams, technology decisions, security/deployment assumptions, roadmap and source references. It contains no runnable business feature acceptance.

Excluded from that design phase: employee execution, new agent prompts/providers, AI memory or learning behavior, functional departments, workflow execution, live external integration, billing, marketplace, self-modifying code, deployment or database migration on the owner's machine. Existing code belongs to later implementation phases; its existence must never rewrite what architecture-only meant.

Phase0 is the original foundation/infrastructure phase. Phase1 adds platform core. Business/AI behavior starts with the relevant later phases. The original V1 request specified a broader infrastructure stack; current personal-use ADRs explicitly select fewer processes, rather than claiming Neo4j/RabbitMQ/MinIO/Kubernetes are deployed. Section15 maps each divergence and exit condition.

Research ambitions such as general organizational intelligence, causal optimization, universal digital twins and benchmark superiority are hypotheses and future Phase12 experiments. A deterministic threshold simulator, historical reflection or descriptive cultural charter cannot prove them. Before/after evidence describes observations; controlled reproducible evaluation is required for causal or comparative claims.

Unsupported expansion risks: additional services create operating/secrets/backup dependencies; paid models create real spend independent of virtual credits; autonomous changes can defeat separation of authority; universal metrics can reward fabricated outcomes; premature production adds TLS/vault/on-call obligations. Enter each idea in the backlog with dependencies, owner, acceptance evidence and a separate scope decision. Do not extend this Sections12–20 batch into Section21+ business work.

Source reconciliation: recovered original V1 prompt explicitly asks Phase−1 architecture only; V2 adds architecture sections and the original roadmap separately defines Phases0–12. These recovered requirements are checked in this batch. The complete generated original blueprint remains unavailable: exact text fidelity is unverified, not reconstructed or certified.
