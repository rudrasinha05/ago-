"""Transactional PostgreSQL persistence for M2 organization and memory."""

from __future__ import annotations

from uuid import UUID

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.memory import MemoryRecord
from ago.organization import Department, Employee


class OrganizationStore:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def add_department(self, *, tenant_id: str, name: str) -> Department:
        from uuid import uuid4

        if not name.strip():
            raise ValueError("Department name required")
        record = Department(str(uuid4()), str(UUID(tenant_id)), name.strip())
        with self.connection.transaction():
            self.connection.execute(
                "INSERT INTO ago_departments(id, tenant_id, name) VALUES (%s, %s, %s)",
                (record.id, record.tenant_id, record.name),
            )
        return record

    def hire(
        self,
        *,
        tenant_id: str,
        department_id: str,
        name: str,
        kind: str,
        manager_id: str | None = None,
    ) -> Employee:
        from uuid import uuid4

        if not name.strip() or kind not in ("human", "ai"):
            raise ValueError("Invalid employee")
        for identifier in (tenant_id, department_id):
            UUID(identifier)
        if manager_id is not None:
            UUID(manager_id)
        record = Employee(str(uuid4()), tenant_id, department_id, name.strip(), kind, manager_id)
        with self.connection.transaction():
            if manager_id:
                manager = self.connection.execute(
                    """SELECT 1 FROM ago_employees
                       WHERE tenant_id=%s AND department_id=%s AND id=%s""",
                    (tenant_id, department_id, manager_id),
                ).fetchone()
                if manager is None:
                    raise ValueError("Manager must belong to same department")
            self.connection.execute(
                """INSERT INTO ago_employees
                   (id, tenant_id, department_id, name, kind, manager_id)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (record.id, tenant_id, department_id, record.name, kind, manager_id),
            )
        return record

    def list_departments(self, *, tenant_id: str) -> list[Department]:
        rows = self.connection.execute(
            "SELECT id, tenant_id, name FROM ago_departments WHERE tenant_id=%s ORDER BY name",
            (tenant_id,),
        ).fetchall()
        return [Department(str(row["id"]), str(row["tenant_id"]), row["name"]) for row in rows]

    def list_employees(self, *, tenant_id: str, department_id: str) -> list[Employee]:
        rows = self.connection.execute(
            """SELECT id, tenant_id, department_id, name, kind, manager_id
               FROM ago_employees WHERE tenant_id=%s AND department_id=%s ORDER BY name""",
            (tenant_id, department_id),
        ).fetchall()
        return [
            Employee(
                str(r["id"]),
                str(r["tenant_id"]),
                str(r["department_id"]),
                r["name"],
                r["kind"],
                str(r["manager_id"]) if r["manager_id"] else None,
            )
            for r in rows
        ]


class MemoryStore:
    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def save(self, record: MemoryRecord) -> None:
        with self.connection.transaction():
            self.connection.execute(
                """INSERT INTO ago_memory_records
                   (id, tenant_id, owner_id, content, visibility)
                   VALUES (%s, %s, %s, %s, %s)""",
                (
                    str(UUID(record.id)),
                    str(UUID(record.tenant_id)),
                    str(UUID(record.owner_id)),
                    record.content,
                    record.visibility,
                ),
            )

    def get(self, *, record_id: str, tenant_id: str, reader_id: str) -> MemoryRecord:
        row = self.connection.execute(
            """SELECT id, tenant_id, owner_id, content, visibility
               FROM ago_memory_records WHERE id=%s AND tenant_id=%s""",
            (record_id, tenant_id),
        ).fetchone()
        if row is None:
            raise LookupError("Memory not found")
        record = MemoryRecord(
            str(row["id"]),
            str(row["tenant_id"]),
            str(row["owner_id"]),
            row["content"],
            row["visibility"],
        )
        record.read(tenant_id=tenant_id, reader_id=reader_id)
        return record
