"""PROJ-014 persistence: module plans, units and integrated source versions.

The caller owns the transaction. Rows are evidence: plans and units are never
deleted, source versions are append-only, and a unit only moves forward.
"""
from __future__ import annotations

import json
from uuid import uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope


class ProjectModuleStore:
    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    # -- reads ---------------------------------------------------------------

    def project(self, tenant_id: str, project_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT i.id,i.founder_id,i.title,i.brief FROM ago_founder_intakes i
               WHERE i.tenant_id=%s AND i.id=%s""", (tenant_id, project_id)).fetchone()
        return dict(row) if row else None

    def plan(self, tenant_id: str, project_id: str, *, lock: bool = False) -> dict | None:
        row = self.connection.execute(
            """SELECT id,project_id,source,deferred,status,decided_by,decided_at,created_at
               FROM ago_project_module_plans WHERE tenant_id=%s AND project_id=%s"""
            + (" FOR UPDATE" if lock else ""), (tenant_id, project_id)).fetchone()
        return dict(row) if row else None

    def units(self, tenant_id: str, plan_id: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT u.id,u.position,u.code,u.title,u.goal,u.status,u.base_version,
                      u.started_at,u.integrated_at,v.version,v.unittest_cases
               FROM ago_project_units u
               LEFT JOIN ago_project_source_versions v ON v.tenant_id=u.tenant_id AND v.unit_id=u.id
               WHERE u.tenant_id=%s AND u.plan_id=%s ORDER BY u.position""",
            (tenant_id, plan_id)).fetchall()]

    def active_unit(self, tenant_id: str, project_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT u.id,u.plan_id,u.position,u.code,u.title,u.goal,u.status,u.base_version
               FROM ago_project_units u
               JOIN ago_project_module_plans p ON p.tenant_id=u.tenant_id AND p.id=u.plan_id
               WHERE u.tenant_id=%s AND u.project_id=%s AND u.status='in_progress'
                 AND p.status='approved'""", (tenant_id, project_id)).fetchone()
        return dict(row) if row else None

    def latest_version(self, tenant_id: str, project_id: str) -> dict | None:
        row = self.connection.execute(
            """SELECT version,files,files_sha256,unittest_cases,unit_id,task_id,created_at
               FROM ago_project_source_versions WHERE tenant_id=%s AND project_id=%s
               ORDER BY version DESC LIMIT 1""", (tenant_id, project_id)).fetchone()
        return dict(row) if row else None

    # -- writes --------------------------------------------------------------

    def insert_plan(self, tenant_id: str, project_id: str, *, source: str, deferred: str,
                    units: list[dict]) -> str:
        plan_id = str(uuid4())
        self.connection.execute(
            """INSERT INTO ago_project_module_plans(id,tenant_id,project_id,source,deferred)
               VALUES (%s,%s,%s,%s,%s)""", (plan_id, tenant_id, project_id, source, deferred[:2000]))
        for position, unit in enumerate(units):
            self.connection.execute(
                """INSERT INTO ago_project_units(id,tenant_id,plan_id,project_id,position,code,title,goal)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                (str(uuid4()), tenant_id, plan_id, project_id, position, unit["code"],
                 unit["title"][:160], unit["goal"][:600]))
        return plan_id

    def approve_plan(self, tenant_id: str, plan_id: str, founder_id: str) -> None:
        self.connection.execute(
            """UPDATE ago_project_module_plans SET status='approved',decided_by=%s,
                      decided_at=clock_timestamp()
               WHERE tenant_id=%s AND id=%s AND status='proposed'""",
            (founder_id, tenant_id, plan_id))

    def start_unit(self, tenant_id: str, unit_id: str, base_version: int) -> None:
        if self.connection.execute(
                """UPDATE ago_project_units SET status='in_progress',base_version=%s,
                          started_at=clock_timestamp()
                   WHERE tenant_id=%s AND id=%s AND status='planned'""",
                (base_version, tenant_id, unit_id)).rowcount != 1:
            raise ValueError("This unit was already started")

    def integrate(self, tenant_id: str, project_id: str, *, unit_id: str, task_id: str,
                  version: int, files: list[dict], files_sha256: str, cases: int) -> None:
        self.connection.execute(
            """INSERT INTO ago_project_source_versions
               (id,tenant_id,project_id,version,unit_id,task_id,files,files_sha256,unittest_cases)
               VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
            (str(uuid4()), tenant_id, project_id, version, unit_id, task_id, json.dumps(files),
             files_sha256, cases))
        if self.connection.execute(
                """UPDATE ago_project_units SET status='integrated',integrated_at=clock_timestamp()
                   WHERE tenant_id=%s AND id=%s AND status='in_progress'""",
                (tenant_id, unit_id)).rowcount != 1:
            raise ValueError("This unit is not the one in progress")

    def task_test(self, tenant_id: str, task_id: str) -> dict | None:
        """The finished isolated test receipt of a stage task, if any."""
        row = self.connection.execute(
            """SELECT status,unittest_cases,candidate_sha256 FROM ago_stage_candidate_tests
               WHERE tenant_id=%s AND task_id=%s ORDER BY created_at DESC LIMIT 1""",
            (tenant_id, task_id)).fetchone()
        return dict(row) if row else None

    def link_unit_task(self, tenant_id: str, *, unit_id: str, plan_step_id: str,
                       previous_task_id: str, task_id: str) -> None:
        """Record the next unit's task, then move the implementation step to it."""
        self.connection.execute(
            """INSERT INTO ago_project_unit_tasks(tenant_id,unit_id,plan_step_id,previous_task_id,task_id)
               VALUES (%s,%s,%s,%s,%s)""", (tenant_id, unit_id, plan_step_id, previous_task_id, task_id))
        if self.connection.execute(
                """UPDATE ago_plan_steps SET task_id=%s
                   WHERE tenant_id=%s AND id=%s AND task_id=%s""",
                (task_id, tenant_id, plan_step_id, previous_task_id)).rowcount != 1:
            raise ValueError("The implementation step changed; refresh first")
