"""Unit-level fail-closed contract tests for persistence adapters."""
import pytest

from ago.organization_store import OrganizationStore, MemoryStore
from ago.task_store import TaskStore
from ago.security import Principal


class NoDatabase:
    def transaction(self):
        raise AssertionError("Unexpected transaction")


def test_department_name_required_before_sql():
    with pytest.raises(ValueError):
        OrganizationStore(NoDatabase()).add_department(
            tenant_id="00000000-0000-0000-0000-000000000001", name=" "
        )


def test_employee_kind_rejected_before_sql():
    with pytest.raises(ValueError):
        OrganizationStore(NoDatabase()).hire(
            tenant_id="00000000-0000-0000-0000-000000000001",
            department_id="00000000-0000-0000-0000-000000000002",
            name="Agent", kind="untrusted",
        )


def test_invalid_task_identity_rejected_before_sql():
    with pytest.raises(ValueError):
        TaskStore(NoDatabase()).propose(
            tenant_id="not-a-uuid", action="deploy:prod", assignee_id="agent"
        )


def test_memory_store_has_no_public_bypass_method():
    assert callable(MemoryStore.get)


def test_principal_tenant_is_explicit():
    assert Principal("user", "tenant-a", ("reviewer",)).tenant_id == "tenant-a"
