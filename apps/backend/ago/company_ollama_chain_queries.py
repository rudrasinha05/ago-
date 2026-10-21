"""Persistence-only tenant-scoped verification of appointed local AGO AI identities."""
from __future__ import annotations

import os
from uuid import UUID

from ago.backend_contracts import DatabaseConnection, RepositoryScope

class CompanyOllamaChainQueries:
    def __init__(self, db: DatabaseConnection,
                 *, repositories: RepositoryScope | None = None):
        self.db=db

    def assignments(self, *, tenant_id: str, actor_id: str, task) -> list[dict]:
        UUID(tenant_id)
        UUID(actor_id)
        UUID(task.id)
        project=task.project_context
        if not project:
            raise PermissionError("Approved founder project discovery task required")
        UUID(str(project["intake_id"]))
        row=self.db.execute("""
            SELECT i.id,i.title,i.founder_id,p.status AS plan_status,
                   l.accountable_manager_id
            FROM ago_founder_intakes i
            JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
              AND l.intake_id=i.id
            JOIN ago_founder_intake_stages s ON s.tenant_id=i.tenant_id
              AND s.intake_id=i.id AND s.stage='discovery'
            JOIN ago_plan_steps ps ON ps.tenant_id=s.tenant_id
              AND ps.plan_id=s.plan_id AND ps.id=s.plan_step_id
            WHERE i.tenant_id=%s AND i.id=%s AND i.founder_id=%s
              AND ps.task_id=%s
        """,(tenant_id,str(project["intake_id"]),actor_id,task.id)).fetchone()
        if row is None or row["plan_status"]!="active":
            raise PermissionError("Founder-owned ACTIVE plan and linked discovery task required")
        full_board=os.getenv("AGO_LOCAL_FULL_BOARD_REVIEW", "").lower()=="true"
        if full_board and os.getenv("AGO_ENVIRONMENT","development").lower() not in (
            "development", "test", "testing"
        ):
            raise PermissionError("Five-seat local Board review is not enabled outside local development")
        board_seats=["Strategy & Vision","Technology Oversight"]
        if full_board:
            board_seats+=["Finance & Budget","Risk & Compliance","Quality & Release"]
        # Fixed, bounded seat names; the SQL placeholders never contain user input.
        placeholders=",".join(["%s"]*len(board_seats))
        seats=self.db.execute("""
            SELECT b.seat,e.id,e.name,e.kind
            FROM ago_company_board_appointments b
            JOIN ago_employees e ON e.tenant_id=b.tenant_id
              AND e.id=b.employee_id
            WHERE b.tenant_id=%s AND b.seat IN (""" + placeholders + """)
        """,tuple([tenant_id]+board_seats)).fetchall()
        board={r["seat"]:dict(r) for r in seats}
        if not set(board_seats) <= board.keys():
            raise PermissionError("Founder must appoint all required real AI Board seats")
        worker=self.db.execute("""
            SELECT e.id,e.name,e.kind,t.action
            FROM ago_governed_tasks t
            JOIN ago_employees e ON e.tenant_id=t.tenant_id
              AND e.id=t.assignee_id
            WHERE t.tenant_id=%s AND t.id=%s
        """,(tenant_id,task.id)).fetchone()
        pm=self.db.execute("""
            SELECT id,name,kind FROM ago_employees
            WHERE tenant_id=%s AND id=%s
        """,(tenant_id,row["accountable_manager_id"])).fetchone()
        if not pm or not worker or worker["action"]!="internal:brief":
            raise PermissionError("Real accountable PM and discovery assignee required")
        ordered=[
            {"role":"ceo",**board["Strategy & Vision"]},
            {"role":"cto",**board["Technology Oversight"]},
        ]
        if full_board:
            ordered.extend([
                {"role":"finance",**board["Finance & Budget"]},
                {"role":"risk",**board["Risk & Compliance"]},
                {"role":"quality",**board["Quality & Release"]},
            ])
        ordered.extend([
            {"role":"pm",**dict(pm)},
            {"role":"employee",**dict(worker)},
        ])
        # Five-seat AI Board membership creates no human credentials, RBAC or
        # publication powers. Distinct, existing identities are mandatory.
        if any(item["kind"]!="ai" for item in ordered):
            raise PermissionError("Board, PM and worker must be actual AI employees")
        if len({str(item["id"]) for item in ordered})!=len(ordered):
            raise PermissionError("All Board, PM and worker roles need distinct employees")
        return [{"role":item["role"],"employee_id":str(item["id"]),
                 "employee_name":item["name"]} for item in ordered]

