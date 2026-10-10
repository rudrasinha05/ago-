"""M5: proposed organizational evolution, human approval, no self-modification."""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository


class ExperimentStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def propose(
        self, *, tenant_id: str, proposer_id: str, hypothesis: str, baseline: str, candidate: str
    ) -> dict:
        UUID(tenant_id)
        UUID(proposer_id)
        if any(
            not value.strip() or len(value) > 2000 for value in (hypothesis, baseline, candidate)
        ):
            raise ValueError("Experiment text must be 1–2000 characters")
        with self.db.transaction():
            experiment_id = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=tenant_id,
                requester_id=proposer_id,
                action=f"policy:experiment:{experiment_id}",
            )
            self.db.execute(
                """INSERT INTO ago_policy_experiments
                   (id,tenant_id,proposer_id,hypothesis,baseline,candidate,approval_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    experiment_id,
                    tenant_id,
                    proposer_id,
                    hypothesis.strip(),
                    baseline.strip(),
                    candidate.strip(),
                    approval.request_id,
                ),
            )
        return {
            "id": experiment_id,
            "approval_id": approval.request_id,
            "status": "pending_approval",
            "applied": False,
        }

    def list(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT e.id,e.hypothesis,e.baseline,e.candidate,e.approval_id,
                      a.status AS approval_status,e.created_at
               FROM ago_policy_experiments e
               JOIN ago_approval_requests a
                 ON a.id=e.approval_id AND a.tenant_id=e.tenant_id
               WHERE e.tenant_id=%s ORDER BY e.created_at DESC,e.id""",
                (tenant_id,),
            ).fetchall()
        ]
