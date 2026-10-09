import pytest
from ago.organization import Organization
from ago.workflows import GovernedTask, TaskStatus
from ago.quality import Review, Verdict
from ago.memory import MemoryRecord


def test_organization_hierarchy():
    org = Organization("tenant-a")
    dept = org.add_department("Engineering")
    with pytest.raises(ValueError):
        org.add_department("engineering")
    manager = org.hire(name="Lead", department_id=dept.id, kind="human")
    worker = org.hire(name="Agent", department_id=dept.id, kind="ai", manager_id=manager.id)
    assert worker.manager_id == manager.id
    with pytest.raises(ValueError):
        org.hire(name="Wrong", department_id=dept.id, kind="ai", manager_id="missing")


def test_workflow_fail_closed():
    task = GovernedTask.propose("tenant-a", "deploy:prod", "agent")
    with pytest.raises(PermissionError):
        task.start()
    task = task.request_approval("approval-1")
    with pytest.raises(PermissionError):
        task.authorize(approved_request_id="other", tenant_id="tenant-a", action="deploy:prod")
    with pytest.raises(PermissionError):
        task.authorize(approved_request_id="approval-1", tenant_id="tenant-b", action="deploy:prod")
    task = task.authorize(approved_request_id="approval-1", tenant_id="tenant-a", action="deploy:prod")
    assert task.start().finish(success=True).status == TaskStatus.COMPLETED


def test_quality_independence():
    with pytest.raises(PermissionError):
        Review("t", "a", "same", "same", Verdict.PASS, "evidence")
    review = Review("t", "a", "author", "reviewer", Verdict.PASS, "checks")
    review.assert_accepted(tenant_id="t", artifact_id="a")
    with pytest.raises(PermissionError):
        review.assert_accepted(tenant_id="other", artifact_id="a")


def test_memory_isolation():
    record = MemoryRecord.create(tenant_id="t", owner_id="owner", content="secret")
    assert record.read(tenant_id="t", reader_id="owner") == "secret"
    with pytest.raises(PermissionError):
        record.read(tenant_id="t", reader_id="other")
    with pytest.raises(PermissionError):
        record.read(tenant_id="other", reader_id="owner")
