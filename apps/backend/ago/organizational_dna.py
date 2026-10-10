"""M7 versioned organizational operating DNA.

DNA only tunes evidence thresholds; it never disables Constitution or human approval.
"""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.dna_domain import (
    BASELINE_PROFILE as BASELINE_PROFILE,
)
from ago.dna_domain import (
    validate_profile as validate_profile,
)
from ago.governance import ApprovalRepository


class GenomeStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def propose(
        self,
        *,
        tenant_id: str,
        proposer_id: str,
        profile: dict,
        rationale: str,
    ) -> dict:
        tenant_id, proposer_id = str(UUID(tenant_id)), str(UUID(proposer_id))
        profile = validate_profile(profile)
        if not 1 <= len(rationale.strip()) <= 3000:
            raise ValueError("DNA candidate requires a rationale")
        with self.db.transaction():
            # Tenant row lock serializes version allocation across concurrent proposers.
            owner = self.db.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                (tenant_id,),
            ).fetchone()
            if owner is None:
                raise LookupError("Tenant not found")
            version = self.db.execute(
                """SELECT COALESCE(MAX(version),0)+1 AS next_version
                   FROM ago_dna_versions WHERE tenant_id=%s""",
                (tenant_id,),
            ).fetchone()["next_version"]
            genome_id = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=tenant_id,
                action=f"dna:activate:{genome_id}",
                requester_id=proposer_id,
            )
            self.db.execute(
                """INSERT INTO ago_dna_versions
                   (id,tenant_id,version,proposer_id,profile,rationale,approval_id)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (
                    genome_id,
                    tenant_id,
                    version,
                    proposer_id,
                    json.dumps(profile, sort_keys=True),
                    rationale.strip(),
                    approval.request_id,
                ),
            )
        return {
            "id": genome_id,
            "version": version,
            "status": "proposed",
            "approval_id": approval.request_id,
            "profile": profile,
        }

    def reconcile(self, *, tenant_id: str, genome_id: str) -> dict:
        tenant_id, genome_id = str(UUID(tenant_id)), str(UUID(genome_id))
        with self.db.transaction():
            tenant = self.db.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                (tenant_id,),
            ).fetchone()
            if tenant is None:
                raise LookupError("Tenant not found")
            genome = self.db.execute(
                """SELECT status,approval_id,version FROM ago_dna_versions
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (tenant_id, genome_id),
            ).fetchone()
            if genome is None:
                raise LookupError("DNA candidate not found")
            if genome["status"] != "proposed":
                raise PermissionError("DNA version is already finalized")
            decision = self.db.execute(
                """SELECT status,action FROM ago_approval_requests
                   WHERE tenant_id=%s AND id=%s FOR SHARE""",
                (tenant_id, genome["approval_id"]),
            ).fetchone()
            if decision is None or decision["action"] != f"dna:activate:{genome_id}":
                raise PermissionError("Matching scoped M2 approval required")
            if decision["status"] == "approved":
                self.db.execute(
                    """UPDATE ago_dna_versions SET status='superseded'
                       WHERE tenant_id=%s AND status='active'""",
                    (tenant_id,),
                )
                self.db.execute(
                    """UPDATE ago_dna_versions
                       SET status='active',activated_at=now()
                       WHERE tenant_id=%s AND id=%s""",
                    (tenant_id, genome_id),
                )
                result = "active"
            elif decision["status"] == "rejected":
                self.db.execute(
                    """UPDATE ago_dna_versions SET status='rejected'
                       WHERE tenant_id=%s AND id=%s""",
                    (tenant_id, genome_id),
                )
                result = "rejected"
            else:
                raise PermissionError("Independent human decision is pending")
        return {"id": genome_id, "version": genome["version"], "status": result}

    def active(self, *, tenant_id: str) -> dict:
        row = self.db.execute(
            """SELECT id,version,profile,activated_at FROM ago_dna_versions
               WHERE tenant_id=%s AND status='active'""",
            (tenant_id,),
        ).fetchone()
        if row is None:
            return {
                "id": None,
                "version": None,
                "profile": dict(BASELINE_PROFILE),
                "source": "baseline",
            }
        return {
            "id": str(row["id"]),
            "version": row["version"],
            "profile": validate_profile(row["profile"]),
            "source": "approved",
            "activated_at": row["activated_at"],
        }

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid DNA list limit")
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT id,version,proposer_id,profile,rationale,approval_id,
                      status,activated_at,created_at
               FROM ago_dna_versions WHERE tenant_id=%s
               ORDER BY version DESC LIMIT %s""",
                (tenant_id, limit),
            ).fetchall()
        ]
