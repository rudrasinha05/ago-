"""Trusted execution adapters cannot execute without approved durable task claim."""
import pytest

from ago.execution import GovernedExecutor
from ago.security import Principal
from ago.workflows import GovernedTask, TaskStatus


class FakeTaskStore:
    def __init__(self, *, approved=True):
        self.approved = approved
        self.finished = []

    def authorize_and_start(self, *, task_id, principal):
        if not self.approved:
            raise PermissionError("Not authorized")
        return GovernedTask(task_id, principal.tenant_id, "internal:inspect",
                            "agent", TaskStatus.RUNNING, "approval")

    def finish(self, *, task_id, tenant_id, success):
        self.finished.append((task_id, tenant_id, success))


def actor():
    return Principal("human", "tenant-a", ("executor",))


def test_allowlisted_handler_runs_after_approval():
    store = FakeTaskStore()
    called = []
    def inspect(task):
        called.append(task.id)
        return {"ok": True}
    result = GovernedExecutor(
        store, handlers={"internal:inspect": inspect},
    ).run(task_id="task", principal=actor())
    assert result.success and result.result == {"ok": True}
    assert called == ["task"]
    assert store.finished == [("task", "tenant-a", True)]


def test_unapproved_task_does_not_call_handler():
    store = FakeTaskStore(approved=False)
    called = []
    with pytest.raises(PermissionError):
        GovernedExecutor(
            store, handlers={"internal:inspect": lambda task: called.append(task)},
        ).run(task_id="task", principal=actor())
    assert not called
    assert not store.finished


def test_unregistered_action_is_not_executed():
    store = FakeTaskStore()
    with pytest.raises(PermissionError):
        GovernedExecutor(store).run(task_id="task", principal=actor())
    assert store.finished == [("task", "tenant-a", False)]


def test_handler_failure_marks_task_failed():
    store = FakeTaskStore()
    def fail(_task):
        raise RuntimeError("underlying tool secret")
    with pytest.raises(RuntimeError, match="Trusted action handler failed"):
        GovernedExecutor(
            store, handlers={"internal:inspect": fail},
        ).run(task_id="task", principal=actor())
    assert store.finished == [("task", "tenant-a", False)]
