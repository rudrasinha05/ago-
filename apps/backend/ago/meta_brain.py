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
