"""M7 versioned organizational operating DNA.

DNA carries governed culture and thresholds; it never grants permissions or disables controls.
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
from ago.dna_domain import CORE_GUARDS, DEFAULT_CHARTER, inherit_dna, validate_charter
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
        charter: dict | None = None,
        scope_kind: str = "company",
        scope_id: str | None = None,
    ) -> dict:
        tenant_id, proposer_id = str(UUID(tenant_id)), str(UUID(proposer_id))
        profile = validate_profile(profile)
        if scope_kind not in ("company", "department", "employee"):
            raise ValueError("Unknown DNA scope")
        if (scope_kind == "company") != (scope_id is None):
            raise ValueError("Scoped DNA requires an exact target")
        scope_id = str(UUID(scope_id)) if scope_id else None
        charter = validate_charter(
            charter if charter is not None else dict(DEFAULT_CHARTER)
            if scope_kind == "company" else {}, override=scope_kind != "company",
        )
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
            if scope_kind != "company":
                parent = self.effective(tenant_id=tenant_id, department_id=scope_id
                    if scope_kind == "department" else None,
                    employee_id=scope_id if scope_kind == "employee" else None,
                    exclude_kind=scope_kind)
                inherit_dna(parent, profile, charter)
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
                   (id,tenant_id,version,proposer_id,profile,rationale,approval_id,
                    charter,scope_kind,scope_id)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s,%s,%s::jsonb,%s,%s)""",
                (
                    genome_id,
                    tenant_id,
                    version,
                    proposer_id,
                    json.dumps(profile, sort_keys=True),
                    rationale.strip(),
                    approval.request_id,
                    json.dumps(charter, sort_keys=True), scope_kind, scope_id,
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
                """SELECT status,approval_id,version,scope_kind,scope_id,profile,charter FROM ago_dna_versions
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
                if genome["scope_kind"] != "company":
                    parent = self.effective(tenant_id=tenant_id,
                        department_id=str(genome["scope_id"])
                        if genome["scope_kind"] == "department" else None,
                        employee_id=str(genome["scope_id"])
                        if genome["scope_kind"] == "employee" else None,
                        exclude_kind=genome["scope_kind"])
                    inherit_dna(parent, genome["profile"], genome["charter"])
                self.db.execute(
                    """UPDATE ago_dna_versions SET status='superseded'
                       WHERE tenant_id=%s AND status='active' AND scope_kind=%s
                         AND scope_id IS NOT DISTINCT FROM %s::uuid""",
                    (tenant_id, genome['scope_kind'], genome['scope_id']),
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
            """SELECT id,version,profile,charter,activated_at FROM ago_dna_versions
               WHERE tenant_id=%s AND status='active' AND scope_kind='company'""",
            (str(UUID(tenant_id)),),
        ).fetchone()
        if row is None:
            return {
                "id": None,
                "version": None,
                "profile": dict(BASELINE_PROFILE),
                "source": "baseline",
                "charter": dict(DEFAULT_CHARTER), "guards": dict(CORE_GUARDS),
            }
        return {
            "id": str(row["id"]),
            "version": row["version"],
            "profile": validate_profile(row["profile"]),
            "source": "approved",
            "charter": validate_charter(row["charter"] or dict(DEFAULT_CHARTER)),
            "guards": dict(CORE_GUARDS),
            "activated_at": row["activated_at"],
        }

    def list(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid DNA list limit")
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT id,version,proposer_id,profile,rationale,approval_id,
                      status,activated_at,created_at,charter,scope_kind,scope_id
               FROM ago_dna_versions WHERE tenant_id=%s
               ORDER BY version DESC LIMIT %s""",
                (tenant_id, limit),
            ).fetchall()
        ]


    def effective(self, *, tenant_id: str, department_id: str | None = None,
                  employee_id: str | None = None, exclude_kind: str | None = None) -> dict:
        tenant_id = str(UUID(tenant_id))
        if employee_id:
            row = self.db.execute(
                "SELECT department_id FROM ago_employees WHERE tenant_id=%s AND id=%s",
                (tenant_id, str(UUID(employee_id))),
            ).fetchone()
            if row is None:
                raise LookupError("Employee not found")
            actual = str(row["department_id"])
            if department_id and actual != str(UUID(department_id)):
                raise PermissionError("Employee must belong to selected department")
            department_id = actual
        if department_id and self.db.execute(
            "SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s",
            (tenant_id, str(UUID(department_id))),
        ).fetchone() is None:
            raise LookupError("Department not found")
        company = self.active(tenant_id=tenant_id)
        result = {"profile": company["profile"], "charter": company["charter"],
                  "guards": dict(CORE_GUARDS), "lineage": [{"scope": "company",
                  "id": company["id"], "version": company["version"]}], "ignored": []}
        for kind, target in (("department", department_id), ("employee", employee_id)):
            if not target or exclude_kind == kind:
                continue
            child = self.db.execute(
                """SELECT id,version,profile,charter FROM ago_dna_versions
                   WHERE tenant_id=%s AND scope_kind=%s AND scope_id=%s AND status='active'""",
                (tenant_id, kind, str(UUID(target))),
            ).fetchone()
            if child:
                try:
                    inherited = inherit_dna(result, child["profile"], child["charter"])
                except PermissionError:
                    result["ignored"].append({"id": str(child["id"]),
                                              "reason": "parent_now_stricter"})
                    continue
                result.update(inherited)
                result["lineage"].append({"scope": kind, "id": str(child["id"]),
                                           "version": child["version"]})
        return result
