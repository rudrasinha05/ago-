"""Persistence-only tenant-scoped verification of appointed local AGO AI identities."""
from __future__ import annotations

import os
from types import SimpleNamespace
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
        if (os.getenv("AGO_LOCAL_ENGINEERING_CANDIDATES")=="true"
                and not full_board):
            raise PermissionError(
                "Engineering generation needs five real reviewed Board seats"
            )
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
        if full_board:
            # A real corporate hierarchy requires the worker to report up to
            # this exact accountable PM; display titles alone are not enough.
            # The bounded recursive walk also refuses forged cycles.
            chain=self.db.execute("""
                WITH RECURSIVE reporting_chain AS (
                    SELECT e.id,e.manager_id,0 AS depth,ARRAY[e.id] AS visited
                    FROM ago_employees e
                    WHERE e.tenant_id=%s AND e.id=%s
                    UNION ALL
                    SELECT boss.id,boss.manager_id,reporting_chain.depth+1,
                           reporting_chain.visited || boss.id
                    FROM ago_employees boss JOIN reporting_chain
                      ON reporting_chain.manager_id=boss.id
                    WHERE boss.tenant_id=%s AND reporting_chain.depth<25
                      AND NOT boss.id=ANY(reporting_chain.visited)
                )
                SELECT EXISTS(
                    SELECT 1 FROM reporting_chain
                    WHERE id=%s AND depth>0
                ) AS reports_to_manager
            """,(tenant_id,str(worker["id"]),tenant_id,str(pm["id"]))).fetchone()
            if not chain or not chain["reports_to_manager"]:
                raise PermissionError(
                    "Full Board execution requires actual employee-to-PM reporting hierarchy"
                )
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


    def record_verified_handoff(
        self, *, tenant_id: str, founder_id: str, task_id: str, role: str,
        employee_id: str, blocked: bool, participants: list[dict],
    ) -> None:
        """Persist only the fact of a verified role inference, never model text."""
        UUID(tenant_id)
        UUID(founder_id)
        UUID(task_id)
        UUID(employee_id)
        # A caller-supplied list cannot reorder/skip verified stages. The list
        # itself originates from assignments(), and durable receipts must
        # additionally prove that each preceding role completed in order.
        roles = tuple(p.get("role") for p in participants)
        if roles not in (
            ("ceo", "cto", "pm", "employee"),
            ("ceo", "cto", "finance", "risk", "quality", "pm", "employee"),
        ) or len({p.get("employee_id") for p in participants}) != len(roles):
            raise PermissionError("Unrecognized or duplicate AGO role chain")
        if not isinstance(blocked, bool) or (
            blocked and role not in {"ceo", "cto", "finance", "risk", "quality"}
        ):
            raise PermissionError("Only a Board member can block its own handoff")
        if not any(
            p["role"] == role and p["employee_id"] == employee_id
            for p in participants
        ):
            raise PermissionError("Unassigned AI member cannot publish task progress")
        description = (
            "AGO verified local inference for " + role
            + ("; Board requested Founder resolution; independent QA pending."
               if blocked else "; task proposal only; independent QA pending.")
        )
        ordinary = (
            "AGO verified local inference for " + role
            + "; task proposal only; independent QA pending."
        )
        blocked_description = (
            "AGO verified local inference for " + role
            + "; Board requested Founder resolution; independent QA pending."
        )
        with self.db.transaction():
            # Lock the exact governed task so two callbacks/retries cannot
            # duplicate a notification or forge work for a nonexistent task.
            task = self.db.execute("""
                SELECT t.id, i.id AS intake_id
                FROM ago_governed_tasks t
                JOIN ago_plan_steps ps ON ps.tenant_id=t.tenant_id
                  AND ps.task_id=t.id
                JOIN ago_founder_intake_stages s ON s.tenant_id=ps.tenant_id
                  AND s.plan_step_id=ps.id AND s.stage='discovery'
                JOIN ago_founder_intakes i ON i.tenant_id=s.tenant_id
                  AND i.id=s.intake_id AND i.founder_id=%s
                JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id
                  AND p.id=i.plan_id AND p.status='active'
                WHERE t.tenant_id=%s AND t.id=%s
                  AND t.action='internal:brief'
                FOR UPDATE OF t
            """, (founder_id, tenant_id, task_id)).fetchone()
            if task is None:
                raise PermissionError(
                    "Verified worker event requires a real Founder-approved discovery task"
                )
            # An ordered caller-provided list is NOT proof of an appointment.
            # Re-read the actual Founder, Board, PM and worker assignments
            # under the task lock before recording an apparent completion.
            # This prevents an old/stolen roster, cross-project callback, or
            # forged AI employee ID from inflating the visible work counter.
            bound_task = SimpleNamespace(
                id=task_id,
                project_context={"intake_id":str(task["intake_id"])},
            )
            appointed = self.assignments(
                tenant_id=tenant_id, actor_id=founder_id, task=bound_task,
            )
            presented = tuple(
                (p.get("role"),p.get("employee_id")) for p in participants
            )
            verified = tuple(
                (p["role"],p["employee_id"]) for p in appointed
            )
            if presented != verified:
                raise PermissionError(
                    "Role handoff does not match currently appointed AI employees"
                )
            # Strictly ordered, durable handoff: a crashed/replayed worker
            # must never claim later roles before earlier model inferences.
            # A Board objection has no normal completion receipt, so it
            # cannot be ignored by downstream PM/engineer callbacks.
            position = roles.index(role)
            if position:
                predecessor = participants[position - 1]
                predecessor_body = (
                    "AGO verified local inference for " + predecessor["role"]
                    + "; task proposal only; independent QA pending."
                )
                previous = self.db.execute("""
                    SELECT id FROM ago_company_chat
                    WHERE tenant_id=%s AND task_id=%s AND employee_id=%s
                      AND kind='status' AND body=%s
                    LIMIT 1
                """, (tenant_id, task_id, predecessor["employee_id"],
                      predecessor_body)).fetchone()
                if previous is None:
                    raise PermissionError(
                        "Prior real AI role handoff is absent or blocked"
                    )
            # Exactly one outcome for a particular task+employee+role. An
            # identical retry is harmless; an opposing Board outcome cannot
            # create a second unread event or silently undo a veto.
            existing = self.db.execute("""
                SELECT body FROM ago_company_chat
                WHERE tenant_id=%s AND task_id=%s AND employee_id=%s
                  AND kind='status' AND body IN (%s,%s)
                LIMIT 1
            """, (tenant_id, task_id, employee_id, ordinary,
                  blocked_description)).fetchone()
            if existing:
                if existing["body"] != description:
                    raise PermissionError(
                        "Conflicting completed AI role evidence"
                    )
                return
            self.db.execute("""
                INSERT INTO ago_company_chat
                  (tenant_id,channel,author_id,author_name,body,kind,
                   employee_id,task_id)
                VALUES (%s,'global',%s,'AGO local agent runtime',%s,'status',%s,%s)
            """, (tenant_id, founder_id, description, employee_id, task_id))
