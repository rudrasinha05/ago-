# AGO M7 — Meta Brain, Executive Intelligence and Organizational DNA

Frozen six-gate **backend** milestone, preserving AGO Sections 0–35, M1–M6 behavior, the modular-monolith architecture and the single `develop` branch. M8 external integrations, M9 UI and M10 deployment remain separate proposed milestones.

1. **Organizational DNA:** immutable per-tenant, versioned *operating thresholds* (QA target, backlog limit, internal-credit alert). Unknown fields prohibited. No threshold can override human approvals, identity/RBAC or constitutional safeguards.
2. **Independent human authorization:** every candidate DNA version requests a precisely scoped M2 approval; only another active authorized human can approve. Explicit operator activation supersedes the previous active profile transactionally. Rejections are terminal; history cannot be overwritten.
3. **Executive intelligence:** capture immutable, tenant-scoped operational metric snapshots from existing M2–M6 task/QA/credit/approval data, deterministic score and risk flags, including honest insufficient-data status. No unsupported market forecasts or invented KPIs.
4. **Meta Brain recommendations:** deterministic, evidence-linked observations based on recorded snapshots, versioned proposals with distinct M2 human endorsement/rejection; never execute plans, rewrite code, grant rights or modify policies themselves.
5. **What-if evaluation and executive briefing:** compare hypothetical operating thresholds using immutable snapshot data; display a traceable brief and proposed improvements without automatically applying them.
6. **Security, APIs, acceptance:** signed-session, persistent tenant RBAC API; append-only database integrity; idempotence and cross-tenant, concurrency, tamper and self-approval tests, plus complete Python 3.11/3.14 PostgreSQL CI.

The word **Meta Brain** refers to evidence-based organizational decision support, not realized AGI, unsupervised learning, autonomous organizational self-rewriting, model training, production financial projections, or deployment readiness.

Operational scoring weights are explicitly frozen in M7: QA coverage 45%, task completion ratio 35%, and remaining internal-credit capacity 20%. A tenant with no completed tasks receives an `insufficient_data` flag and no fitness score (null), not an artificially high score.

M7 is only accepted after actual GitHub CI demonstrates migrations, Ruff and full regression + real authenticated PostgreSQL integration tests on Python 3.11 and 3.14. No intermediate founder pull requests.
