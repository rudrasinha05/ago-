"""M2 tenant-scoped organization model with explicit hierarchy invariants."""
from __future__ import annotations
from dataclasses import dataclass, field
from uuid import uuid4


@dataclass(frozen=True)
class Department:
    id: str
    tenant_id: str
    name: str


@dataclass(frozen=True)
class Employee:
    id: str
    tenant_id: str
    department_id: str
    name: str
    kind: str
    manager_id: str | None = None


@dataclass
class Organization:
    tenant_id: str
    departments: dict[str, Department] = field(default_factory=dict)
    employees: dict[str, Employee] = field(default_factory=dict)

    def add_department(self, name: str) -> Department:
        if not name.strip() or any(d.name.lower() == name.strip().lower() for d in self.departments.values()):
            raise ValueError("Department name must be unique and nonempty")
        department = Department(str(uuid4()), self.tenant_id, name.strip())
        self.departments[department.id] = department
        return department

    def hire(self, *, name: str, department_id: str, kind: str, manager_id: str | None = None) -> Employee:
        if not name.strip() or kind not in ("human", "ai"):
            raise ValueError("Valid name and employee kind required")
        if department_id not in self.departments:
            raise ValueError("Unknown department")
        if manager_id is not None:
            manager = self.employees.get(manager_id)
            if manager is None or manager.department_id != department_id:
                raise ValueError("Manager must belong to the same department")
        employee = Employee(str(uuid4()), self.tenant_id, department_id, name.strip(), kind, manager_id)
        self.employees[employee.id] = employee
        return employee
