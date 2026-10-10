"""M7 executive operating metrics: deterministic, evidence-linked, tenant-scoped.

Not a business forecast or guarantee. No operations change as a result of scoring.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.architecture_guard import MODULE_DIR, load_policy, verify
from ago.executive_intelligence_queries import ExecutiveIntelligenceQueries
from ago.organizational_dna import GenomeStore, validate_profile


def evaluate(metrics: dict, profile: dict) -> dict:
    """Score frozen M7 evidence at QA 45%, completion 35%, credit capacity 20%."""
    profile = validate_profile(profile)
    mandatory = (
        "total_tasks",
        "completed_tasks",
        "qa_pass",
        "backlog_tasks",
        "budget_ceiling",
        "budget_consumed",
        "budget_configured",
    )
    if any(key not in metrics for key in mandatory):
        raise ValueError("An executive assessment requires complete source metrics")
    total, completed, qa_pass, backlog = (
        metrics["total_tasks"],
        metrics["completed_tasks"],
        metrics["qa_pass"],
        metrics["backlog_tasks"],
    )
    if (
        any(type(v) is not int or v < 0 for v in (total, completed, qa_pass, backlog))
        or completed > total
        or qa_pass > completed
        or backlog > total
    ):
        raise ValueError("Invalid bounded task/QA evidence")
    if type(metrics["budget_configured"]) is not bool:
        raise ValueError("Budget configured flag must be boolean")
    try:
        ceiling = Decimal(str(metrics["budget_ceiling"]))
        consumed = Decimal(str(metrics["budget_consumed"]))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("Invalid virtual-credit values") from exc
    if (
        not ceiling.is_finite()
        or not consumed.is_finite()
        or ceiling < 0
        or consumed < 0
        or consumed > ceiling
    ):
        raise ValueError("Invalid bounded virtual-credit evidence")
    qa_pct = Decimal(100) * qa_pass / completed if completed else Decimal(0)
    completion_pct = Decimal(100) * completed / total if total else Decimal(0)
    utilization_pct = (
        Decimal(100) * consumed / ceiling
        if metrics["budget_configured"] and ceiling
        else Decimal(0)
    )
    risks = []
    if not completed:
        risks.append("insufficient_data")
    elif qa_pct < profile["qa_target_pct"]:
        risks.append("qa_below_target")
    if backlog > profile["backlog_limit"]:
        risks.append("backlog_over_limit")
    if metrics["budget_configured"] and ceiling and utilization_pct >= profile["budget_alert_pct"]:
        risks.append("budget_alert")
    fitness = None
    if completed:
        scored = (
            qa_pct * Decimal("0.45")
            + completion_pct * Decimal("0.35")
            + (Decimal(100) - utilization_pct) * Decimal("0.20")
        )
        fitness = str(scored.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    return {
        "fitness": fitness,
        "risk_flags": risks,
        "quality_pct": str(qa_pct.quantize(Decimal("0.01"))),
        "completion_pct": str(completion_pct.quantize(Decimal("0.01"))),
        "credit_utilization_pct": str(utilization_pct.quantize(Decimal("0.01"))),
        "insufficient_evidence": completed == 0,
        "simulation_only": True,
    }


class ExecutiveIntelligence:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _metrics(self, tenant_id: str) -> dict:
        # One SQL statement provides a statement-level consistent operational view.
        row = (
            self.repositories.resolve(ExecutiveIntelligenceQueries)
            .select_ago_governed_tasks_01((tenant_id,) * 17)
            .fetchone()
        )
        if row is None:
            raise LookupError("Executive metrics query failed")
        return {
            key: int(row[key])
            for key in (
                "total_tasks",
                "completed_tasks",
                "backlog_tasks",
                "qa_pass",
                "pending_approvals",
                "failed_agent_runs",
                "open_handoffs",
                "verified_knowledge",
            )
        } | {
            "budget_configured": row["budget_ceiling"] is not None,
            "budget_ceiling": str(row["budget_ceiling"] or "0"),
            "budget_consumed": str(row["budget_consumed"] or "0"),
            "organization_observation": {k: row[k] for k in
                ("goals", "plans", "strategic_decisions", "departments", "ai_employees", "human_employees", "failed_tasks")},
        }

    def capture(self, *, tenant_id: str, analyst_id: str) -> dict:
        tenant_id, analyst_id = str(UUID(tenant_id)), str(UUID(analyst_id))
        with self.db.transaction():
            active = self.repositories.resolve(GenomeStore).active(tenant_id=tenant_id)
            metrics = self._metrics(tenant_id)
            policy = load_policy()
            architecture = verify(MODULE_DIR, policy)
            metrics["architecture_observation"] = {
                "policy_version": policy["schema_version"], "modules": architecture.modules,
                "edges": len(architecture.edges), "passed": architecture.passed,
                "violations": len(architecture.violations),
                "policy_digest": hashlib.sha256(json.dumps(policy, sort_keys=True).encode()).hexdigest(),
                "source": "packaged_static_dependency_audit",
            }
            assessment = evaluate(metrics, active["profile"])
            evidence = {
                "metrics": metrics,
                "dna_id": active["id"],
                "profile": active["profile"],
                "assessment": assessment,
            }
            digest = hashlib.sha256(
                json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            snapshot_id = str(uuid4())
            self.repositories.resolve(
                ExecutiveIntelligenceQueries
            ).insert_ago_executive_snapshots_02(
                (
                    snapshot_id,
                    tenant_id,
                    analyst_id,
                    active["id"],
                    json.dumps(metrics, sort_keys=True),
                    json.dumps(assessment["risk_flags"]),
                    assessment["fitness"],
                    digest,
                )
            )
        return {
            "id": snapshot_id,
            "digest": digest,
            "dna_id": active["id"],
            "dna_version": active["version"],
            "metrics": metrics,
            **assessment,
            "recorded": True,
        }

    def get(self, *, tenant_id: str, snapshot_id: str) -> dict:
        tenant_id, snapshot_id = str(UUID(tenant_id)), str(UUID(snapshot_id))
        row = (
            self.repositories.resolve(ExecutiveIntelligenceQueries)
            .select_ago_executive_snapshots_03((tenant_id, snapshot_id))
            .fetchone()
        )
        if row is None:
            raise LookupError("Executive snapshot not found")
        result = dict(row)
        result["id"] = str(result["id"])
        result["analyst_id"] = str(result["analyst_id"])
        result["dna_id"] = str(result["dna_id"]) if result["dna_id"] else None
        result["fitness"] = str(result["fitness"]) if result["fitness"] is not None else None
        return result

    def list(self, *, tenant_id: str, limit: int = 50) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid executive snapshot list limit")
        rows = (
            self.repositories.resolve(ExecutiveIntelligenceQueries)
            .select_ago_executive_snapshots_04((tenant_id, limit))
            .fetchall()
        )
        return [
            {
                "id": str(row["id"]),
                "dna_id": str(row["dna_id"]) if row["dna_id"] else None,
                "fitness": str(row["fitness"]) if row["fitness"] is not None else None,
                "risk_flags": row["risk_flags"],
                "digest": row["digest"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def simulate(self, *, tenant_id: str, snapshot_id: str, candidate: dict) -> dict:
        candidate = validate_profile(candidate)
        snapshot = self.get(tenant_id=tenant_id, snapshot_id=snapshot_id)
        return {
            "snapshot_id": snapshot["id"],
            "source_digest": snapshot["digest"],
            "candidate_profile": candidate,
            "assessment": evaluate(snapshot["metrics"], candidate),
            "applied": False,
        }

    def verify(self, *, tenant_id: str, snapshot_id: str) -> dict:
        """Recompute the immutable source digest using frozen historical DNA."""
        snapshot = self.get(tenant_id=tenant_id, snapshot_id=snapshot_id)
        if snapshot["dna_id"]:
            row = (
                self.repositories.resolve(ExecutiveIntelligenceQueries)
                .select_ago_dna_versions_05((tenant_id, snapshot["dna_id"]))
                .fetchone()
            )
            if row is None:
                raise PermissionError("Historical DNA source is missing")
            profile = validate_profile(row["profile"])
        else:
            from ago.organizational_dna import BASELINE_PROFILE

            profile = dict(BASELINE_PROFILE)
        assessment = evaluate(snapshot["metrics"], profile)
        evidence = {
            "metrics": snapshot["metrics"],
            "dna_id": snapshot["dna_id"],
            "profile": profile,
            "assessment": assessment,
        }
        digest = hashlib.sha256(
            json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return {
            "snapshot_id": snapshot["id"],
            "verified": digest == snapshot["digest"],
            "expected_digest": snapshot["digest"],
            "recomputed_digest": digest,
            "advisory_only": True,
        }
