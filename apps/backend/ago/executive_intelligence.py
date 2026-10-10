"""M7 executive operating metrics: deterministic, evidence-linked, tenant-scoped.

Not a business forecast or guarantee. No operations change as a result of scoring.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID, uuid4

from ago.organizational_dna import GenomeStore, validate_profile


def evaluate(metrics: dict, profile: dict) -> dict:
    """Score frozen M7 evidence at QA 45%, completion 35%, credit capacity 20%."""
    profile = validate_profile(profile)
    mandatory = ("total_tasks", "completed_tasks", "qa_pass", "backlog_tasks",
                 "budget_ceiling", "budget_consumed", "budget_configured")
    if any(key not in metrics for key in mandatory):
        raise ValueError("An executive assessment requires complete source metrics")
    total, completed, qa_pass, backlog = (
        metrics["total_tasks"], metrics["completed_tasks"],
        metrics["qa_pass"], metrics["backlog_tasks"],
    )
    if (any(type(v) is not int or v < 0 for v in
            (total, completed, qa_pass, backlog))
            or completed > total or qa_pass > completed or backlog > total):
        raise ValueError("Invalid bounded task/QA evidence")
    if type(metrics["budget_configured"]) is not bool:
        raise ValueError("Budget configured flag must be boolean")
    try:
        ceiling = Decimal(str(metrics["budget_ceiling"]))
        consumed = Decimal(str(metrics["budget_consumed"]))
    except (ValueError, ArithmeticError) as exc:
        raise ValueError("Invalid virtual-credit values") from exc
    if (not ceiling.is_finite() or not consumed.is_finite()
            or ceiling < 0 or consumed < 0 or consumed > ceiling):
        raise ValueError("Invalid bounded virtual-credit evidence")
    qa_pct = Decimal(100) * qa_pass / completed if completed else Decimal(0)
    completion_pct = Decimal(100) * completed / total if total else Decimal(0)
    utilization_pct = (
        Decimal(100) * consumed / ceiling
        if metrics["budget_configured"] and ceiling else Decimal(0)
    )
    risks = []
    if not completed:
        risks.append("insufficient_data")
    elif qa_pct < profile["qa_target_pct"]:
        risks.append("qa_below_target")
    if backlog > profile["backlog_limit"]:
        risks.append("backlog_over_limit")
    if (metrics["budget_configured"] and ceiling
            and utilization_pct >= profile["budget_alert_pct"]):
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
        "fitness": fitness, "risk_flags": risks,
        "quality_pct": str(qa_pct.quantize(Decimal("0.01"))),
        "completion_pct": str(completion_pct.quantize(Decimal("0.01"))),
        "credit_utilization_pct": str(utilization_pct.quantize(Decimal("0.01"))),
        "insufficient_evidence": completed == 0,
        "simulation_only": True,
    }


class ExecutiveIntelligence:
    def __init__(self, db):
        self.db = db

    def _metrics(self, tenant_id: str) -> dict:
        # One SQL statement provides a statement-level consistent operational view.
        row = self.db.execute(
            """SELECT
                (SELECT count(*) FROM ago_governed_tasks
                   WHERE tenant_id=%s) AS total_tasks,
                (SELECT count(*) FROM ago_governed_tasks
                   WHERE tenant_id=%s AND status='completed') AS completed_tasks,
                (SELECT count(*) FROM ago_governed_tasks
                   WHERE tenant_id=%s AND status IN
                     ('proposed','waiting_approval','ready','running')) AS backlog_tasks,
                (SELECT count(*) FROM ago_task_reviews
                   WHERE tenant_id=%s AND verdict='pass') AS qa_pass,
                (SELECT count(*) FROM ago_approval_requests
                   WHERE tenant_id=%s AND status='pending') AS pending_approvals,
                (SELECT count(*) FROM ago_agent_runs
                   WHERE tenant_id=%s AND status='failed') AS failed_agent_runs,
                (SELECT count(*) FROM ago_handoffs
                   WHERE tenant_id=%s AND status='requested') AS open_handoffs,
                (SELECT count(*) FROM ago_knowledge_nodes
                   WHERE tenant_id=%s AND status='verified') AS verified_knowledge,
                (SELECT ceiling FROM ago_credit_budgets
                   WHERE tenant_id=%s) AS budget_ceiling,
                (SELECT consumed FROM ago_credit_budgets
                   WHERE tenant_id=%s) AS budget_consumed""",
            (tenant_id,) * 10,
        ).fetchone()
        if row is None:
            raise LookupError("Executive metrics query failed")
        return {
            key: int(row[key]) for key in (
                "total_tasks", "completed_tasks", "backlog_tasks", "qa_pass",
                "pending_approvals", "failed_agent_runs", "open_handoffs",
                "verified_knowledge",
            )
        } | {
            "budget_configured": row["budget_ceiling"] is not None,
            "budget_ceiling": str(row["budget_ceiling"] or "0"),
            "budget_consumed": str(row["budget_consumed"] or "0"),
        }

    def capture(self, *, tenant_id: str, analyst_id: str) -> dict:
        tenant_id, analyst_id = str(UUID(tenant_id)), str(UUID(analyst_id))
        with self.db.transaction():
            active = GenomeStore(self.db).active(tenant_id=tenant_id)
            metrics = self._metrics(tenant_id)
            assessment = evaluate(metrics, active["profile"])
            evidence = {
                "metrics": metrics, "dna_id": active["id"],
                "profile": active["profile"], "assessment": assessment,
            }
            digest = hashlib.sha256(
                json.dumps(evidence, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            snapshot_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_executive_snapshots
                   (id,tenant_id,analyst_id,dna_id,metrics,risk_flags,fitness,digest)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s)""",
                (snapshot_id, tenant_id, analyst_id, active["id"],
                 json.dumps(metrics, sort_keys=True),
                 json.dumps(assessment["risk_flags"]),
                 assessment["fitness"], digest),
            )
        return {
            "id": snapshot_id, "digest": digest,
            "dna_id": active["id"], "dna_version": active["version"],
            "metrics": metrics, **assessment, "recorded": True,
        }

    def get(self, *, tenant_id: str, snapshot_id: str) -> dict:
        tenant_id, snapshot_id = str(UUID(tenant_id)), str(UUID(snapshot_id))
        row = self.db.execute(
            """SELECT id,analyst_id,dna_id,metrics,risk_flags,fitness,digest,created_at
               FROM ago_executive_snapshots WHERE tenant_id=%s AND id=%s""",
            (tenant_id, snapshot_id),
        ).fetchone()
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
        rows = self.db.execute(
            """SELECT id,dna_id,fitness,risk_flags,digest,created_at
               FROM ago_executive_snapshots WHERE tenant_id=%s
               ORDER BY capture_order DESC LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()
        return [
            {
                "id": str(row["id"]),
                "dna_id": str(row["dna_id"]) if row["dna_id"] else None,
                "fitness": str(row["fitness"]) if row["fitness"] is not None else None,
                "risk_flags": row["risk_flags"],
                "digest": row["digest"], "created_at": row["created_at"],
            }
            for row in rows
        ]

    def simulate(self, *, tenant_id: str, snapshot_id: str, candidate: dict) -> dict:
        candidate = validate_profile(candidate)
        snapshot = self.get(tenant_id=tenant_id, snapshot_id=snapshot_id)
        return {
            "snapshot_id": snapshot["id"], "source_digest": snapshot["digest"],
            "candidate_profile": candidate,
            "assessment": evaluate(snapshot["metrics"], candidate),
            "applied": False,
        }

    def verify(self, *, tenant_id: str, snapshot_id: str) -> dict:
        """Recompute the immutable source digest using frozen historical DNA."""
        snapshot = self.get(tenant_id=tenant_id, snapshot_id=snapshot_id)
        if snapshot["dna_id"]:
            row = self.db.execute(
                """SELECT profile FROM ago_dna_versions
                   WHERE tenant_id=%s AND id=%s""",
                (tenant_id, snapshot["dna_id"]),
            ).fetchone()
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
            "profile": profile, "assessment": assessment,
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
