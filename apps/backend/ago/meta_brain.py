"""M7 Meta Brain: evidence-derived, independently governed executive advice.

It cannot mutate the Constitution, deploy software or execute third-party tools.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.executive_intelligence import ExecutiveIntelligence
from ago.governance import ApprovalRepository
from ago.meta_brain_queries import MetaBrainQueries

ADVICE = {
    "insufficient_data": (
        "Collect independently reviewed task outcomes before comparing "
        "organizational performance or changing operating thresholds."
    ),
    "qa_below_target": (
        "Review QA findings and propose a human-approved quality improvement plan."
    ),
    "backlog_over_limit": (
        "Review uncompleted task ownership and propose a human-approved "
        "coordination or staffing experiment."
    ),
    "budget_alert": (
        "Investigate virtual-credit consumption before authorizing additional "
        "model-assisted tasks; do not assume credits equal monetary spend."
    ),
    "stable_operation": (
        "Continue evidence collection and independent QA; no automatic "
        "structural or policy changes are recommended."
    ),
}


class MetaBrain:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def generate(
        self,
        *,
        tenant_id: str,
        author_id: str,
        snapshot_id: str,
    ) -> list[dict]:
        tenant_id, author_id, snapshot_id = (
            str(UUID(tenant_id)),
            str(UUID(author_id)),
            str(UUID(snapshot_id)),
        )
        with self.db.transaction():
            # Serialize concurrent recommendations for the same immutable evidence.
            row = (
                self.repositories.resolve(MetaBrainQueries)
                .select_ago_executive_snapshots_01((tenant_id, snapshot_id))
                .fetchone()
            )
            if row is None:
                raise LookupError("Executive evidence snapshot not found")
            codes = sorted(set(row["risk_flags"])) or ["stable_operation"]
            if not all(code in ADVICE for code in codes):
                raise ValueError("Unknown risk category in executive evidence")
            for code in codes:
                exists = (
                    self.repositories.resolve(MetaBrainQueries)
                    .select_ago_meta_recommendations_02((tenant_id, snapshot_id, code))
                    .fetchone()
                )
                if exists is not None:
                    continue
                recommendation_id = str(uuid4())
                approval = self.repositories.resolve(ApprovalRepository).propose(
                    tenant_id=tenant_id,
                    requester_id=author_id,
                    action=f"meta:endorse:{recommendation_id}",
                )
                evidence = {
                    "snapshot_digest": row["digest"],
                    "risk_flag": code,
                    "metrics": row["metrics"],
                }
                self.repositories.resolve(MetaBrainQueries).insert_ago_meta_recommendations_03(
                    (
                        recommendation_id,
                        tenant_id,
                        snapshot_id,
                        author_id,
                        code,
                        ADVICE[code],
                        json.dumps(evidence, sort_keys=True),
                        approval.request_id,
                    )
                )
        return self.list(tenant_id=tenant_id, snapshot_id=snapshot_id)

    def reconcile(self, *, tenant_id: str, recommendation_id: str) -> dict:
        tenant_id = str(UUID(tenant_id))
        recommendation_id = str(UUID(recommendation_id))
        with self.db.transaction():
            rec = (
                self.repositories.resolve(MetaBrainQueries)
                .select_ago_meta_recommendations_04((tenant_id, recommendation_id))
                .fetchone()
            )
            if rec is None:
                raise LookupError("Recommendation not found")
            if rec["status"] != "proposed":
                raise PermissionError("Recommendation was already finalized")
            approval = (
                self.repositories.resolve(MetaBrainQueries)
                .select_ago_approval_requests_05((tenant_id, rec["approval_id"]))
                .fetchone()
            )
            if approval is None or approval["action"] != (f"meta:endorse:{recommendation_id}"):
                raise PermissionError("Matching human approval is required")
            if approval["status"] == "approved":
                state = "endorsed"
            elif approval["status"] == "rejected":
                state = "rejected"
            else:
                raise PermissionError("Human endorsement decision is pending")
            self.repositories.resolve(MetaBrainQueries).update_ago_meta_recommendations_06(
                (state, tenant_id, recommendation_id)
            )
        return {"id": recommendation_id, "status": state, "executed": False}

    def list(
        self,
        *,
        tenant_id: str,
        snapshot_id: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if not 1 <= limit <= 200:
            raise ValueError("Invalid recommendation limit")
        args: list = [str(UUID(tenant_id))]
        extra = ""
        if snapshot_id is not None:
            extra = " AND snapshot_id=%s"
            args.append(str(UUID(snapshot_id)))
        args.append(limit)
        rows = (
            self.repositories.resolve(MetaBrainQueries)
            .select_ago_meta_recommendations_07(tuple(args), extra=extra)
            .fetchall()
        )
        return [
            {
                **dict(row),
                "id": str(row["id"]),
                "snapshot_id": str(row["snapshot_id"]),
                "proposer_id": str(row["proposer_id"]),
                "approval_id": str(row["approval_id"]),
            }
            for row in rows
        ]

    def brief(self, *, tenant_id: str) -> dict:
        snapshots = self.repositories.resolve(ExecutiveIntelligence).list(
            tenant_id=tenant_id, limit=1
        )
        if not snapshots:
            return {
                "status": "needs_snapshot",
                "fitness": None,
                "risk_flags": ["insufficient_data"],
                "recommendations": [],
                "advisory_only": True,
            }
        latest = snapshots[0]
        return {
            "status": "review_required" if latest["risk_flags"] else "observed",
            "snapshot": latest,
            "recommendations": self.list(
                tenant_id=tenant_id,
                snapshot_id=latest["id"],
            ),
            "advisory_only": True,
            "automatic_execution": False,
        }


    def reflect(self, *, tenant_id: str, limit: int = 20) -> dict:
        if not 2 <= limit <= 100:
            raise ValueError("Reflection requires a 2–100 snapshot window")
        intelligence = self.repositories.resolve(ExecutiveIntelligence)
        history = intelligence.list(tenant_id=tenant_id, limit=limit)
        history.reverse()
        sources = []
        for item in history:
            if not intelligence.verify(tenant_id=tenant_id, snapshot_id=item["id"])["verified"]:
                raise PermissionError("Unverified reflection source")
            sources.append(intelligence.get(tenant_id=tenant_id, snapshot_id=item["id"]))
        latest = sources[-1] if sources else None
        metrics = latest["metrics"] if latest else {}
        organization = metrics.get("organization_observation")
        architecture = metrics.get("architecture_observation")
        dimensions = {
            "organization": organization or {"status": "needs_extended_snapshot"},
            "architecture": architecture or {"status": "needs_extended_snapshot"},
            "departments": organization.get("departments", []) if organization else [],
            "workforce": {"ai_employees": organization.get("ai_employees"),
                          "human_employees": organization.get("human_employees"),
                          "failed_agent_runs": metrics.get("failed_agent_runs")}
                         if organization else {"status": "needs_extended_snapshot"},
            "workflows": {key: metrics.get(key) for key in
                          ("total_tasks", "completed_tasks", "backlog_tasks", "open_handoffs")},
        }
        findings = []
        if len(sources) >= 2:
            first = sources[0]["metrics"]
            for key, concern, suggestion in (
                ("backlog_tasks", "workflow backlog increased", "Review task ownership and dependencies."),
                ("failed_agent_runs", "failed runs increased", "Inspect failure evidence before changing handlers."),
                ("pending_approvals", "pending decisions increased", "Review independent reviewer capacity."),
                ("open_handoffs", "unresolved handoffs increased", "Review department coordination."),
            ):
                delta = metrics[key] - first[key]
                if delta > 0:
                    findings.append({"metric": key, "observed_delta": delta,
                                     "concern": concern, "proposal": suggestion})
            if architecture and not architecture["passed"]:
                findings.append({"metric": "architecture_violations",
                                 "concern": "packaged dependency contract failed",
                                 "proposal": "Review the frozen module contract before approving changes."})
        recommendations = self.list(tenant_id=tenant_id)
        return {
            "decision_review": {"company_brain_decisions": organization.get("strategic_decisions", []) if organization else [],
                                "proposed": sum(r["status"] == "proposed" for r in recommendations),
                                "endorsed": sum(r["status"] == "endorsed" for r in recommendations),
                                "rejected": sum(r["status"] == "rejected" for r in recommendations),
                                "scope": "first 100 tenant recommendations in stable historical order; latest 100 strategic decisions"},
            "reflection_findings": findings,
            "optimization_policy": "Propose bounded experiments; compare reviewed outcomes before adoption.",
            "status": "observed" if len(sources) >= 2 else "insufficient_history",
            "sample_count": len(sources), "window_limit": limit,
            "source_ids": [s["id"] for s in sources],
            "source_digests": [s["digest"] for s in sources],
            "dimensions": dimensions,
            "timeline": [{"snapshot_id": s["id"], "captured_at": s["created_at"],
                          "dna_id": s["dna_id"], "metrics": s["metrics"],
                          "fitness": s["fitness"]} for s in sources],
            "reviewed_evaluations": [e for e in self.evaluations(tenant_id=tenant_id)
                                      if e["status"] == "verified"],
            "advisory_only": True, "automatic_execution": False,
            "causal_effect_proven": False,
        }

    def propose_evaluation(self, *, tenant_id: str, author_id: str,
                           recommendation_id: str, after_id: str, change_evidence: str) -> dict:
        from decimal import Decimal
        tenant_id, author_id, recommendation_id, after_id = map(str, map(UUID,
            (tenant_id, author_id, recommendation_id, after_id)))
        if not 1 <= len(change_evidence.strip()) <= 3000:
            raise ValueError("Actual organizational change evidence is required")
        queries = self.repositories.resolve(MetaBrainQueries)
        intelligence = self.repositories.resolve(ExecutiveIntelligence)
        with self.db.transaction():
            rec = queries.select_ago_meta_recommendations_04((tenant_id, recommendation_id)).fetchone()
            if rec is None:
                raise LookupError("Recommendation not found")
            if rec["status"] != "endorsed":
                raise PermissionError("An independently endorsed recommendation is required")
            before_id = str(rec["snapshot_id"])
            before = intelligence.get(tenant_id=tenant_id, snapshot_id=before_id)
            after = intelligence.get(tenant_id=tenant_id, snapshot_id=after_id)
            if (after["capture_order"] <= before["capture_order"]
                    or after["created_at"] < rec["decided_at"]):
                raise PermissionError("After evidence must follow the endorsement")
            for snapshot in (before, after):
                if not intelligence.verify(tenant_id=tenant_id,
                                           snapshot_id=snapshot["id"])["verified"]:
                    raise PermissionError("Source digest mismatch")
            from ago.organizational_dna import BASELINE_PROFILE
            # Fixed scoring profile eliminates threshold-change scoring artifacts.
            from ago.executive_intelligence import evaluate
            scored_before = evaluate(before["metrics"], BASELINE_PROFILE)
            scored_after = evaluate(after["metrics"], BASELINE_PROFILE)
            delta = {key: str(Decimal(scored_after[key]) - Decimal(scored_before[key]))
                     for key in ("quality_pct", "completion_pct", "credit_utilization_pct")}
            assessment = {
                "before_digest": before["digest"], "after_digest": after["digest"],
                "before": scored_before, "after": scored_after, "observed_delta": delta,
                "scoring_profile": dict(BASELINE_PROFILE),
                "sufficient_outcomes": not (scored_before["insufficient_evidence"]
                                            or scored_after["insufficient_evidence"]),
                "causal_effect_proven": False, "applied": False,
                "interpretation": "Cumulative observational comparison; independent review required.",
            }
            identifier = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=tenant_id, requester_id=author_id, action=f"meta:evaluate:{identifier}")
            queries.insert_evaluation((identifier, tenant_id, recommendation_id, before_id,
                after_id, author_id, approval.request_id, change_evidence.strip(),
                json.dumps(assessment, sort_keys=True)))
        return {"id": identifier, "approval_id": approval.request_id,
                "status": "proposed", "assessment": assessment}

    def evaluations(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.repositories.resolve(MetaBrainQueries)
                .evaluations((str(UUID(tenant_id)),)).fetchall()]

    def reconcile_evaluation(self, *, tenant_id: str, evaluation_id: str) -> dict:
        tenant_id, evaluation_id = str(UUID(tenant_id)), str(UUID(evaluation_id))
        queries = self.repositories.resolve(MetaBrainQueries)
        with self.db.transaction():
            row = queries.evaluation_for_review((tenant_id, evaluation_id)).fetchone()
            if row is None:
                raise LookupError("Evaluation not found")
            if row["status"] != "proposed":
                raise PermissionError("Evaluation already finalized")
            decision = queries.select_ago_approval_requests_05((tenant_id, row["approval_id"])).fetchone()
            if not decision or decision["action"] != f"meta:evaluate:{evaluation_id}":
                raise PermissionError("Exact evaluation review required")
            statuses = {"approved": "verified", "rejected": "rejected"}
            if decision["status"] not in statuses:
                raise PermissionError("Human evidence review pending")
            state = statuses[decision["status"]]
            queries.finalize_evaluation((state, tenant_id, evaluation_id))
        return {"id": evaluation_id, "status": state,
                "automatic_execution": False, "causal_effect_proven": False}
