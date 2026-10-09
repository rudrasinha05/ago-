"""Integration of tenant RBAC and durable approval gate with task domain."""
import pytest

from ago.governed_execution import GovernanceGate
from ago.security import Principal
from ago.workflows import GovernedTask


class FakeSecurity:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def permitted(self, principal, permission, tenant_id):
        return self.allowed and principal.tenant_id == tenant_id


class FakeApprovals:
    def __init__(self, approved=True):
        self.approved = approved

    def assert_executable(self, *, request_id, tenant_id, action):
        if not self.approved:
            raise PermissionError("Not approved")

    def decide(self, **kwargs):
        return kwargs


def principal(tenant="t"):
    return Principal("reviewer", tenant, ("manager",))


def waiting_task():
    return GovernedTask.propose("t", "deploy:prod", "agent").request_approval("approval-1")


def test_gate_allows_scoped_approved_task():
    gate = GovernanceGate(FakeApprovals(), FakeSecurity())
    ready = gate.authorize_task(waiting_task(), principal=principal())
    assert ready.status.value == "ready"


def test_gate_rejects_unapproved():
    gate = GovernanceGate(FakeApprovals(False), FakeSecurity())
    with pytest.raises(PermissionError):
        gate.authorize_task(waiting_task(), principal=principal())


def test_gate_rejects_missing_rbac():
    gate = GovernanceGate(FakeApprovals(), FakeSecurity(False))
    with pytest.raises(PermissionError):
        gate.authorize_task(waiting_task(), principal=principal())


def test_gate_rejects_cross_tenant():
    gate = GovernanceGate(FakeApprovals(), FakeSecurity())
    with pytest.raises(PermissionError):
        gate.authorize_task(waiting_task(), principal=principal("other"))


def test_decide_requires_rbac():
    gate = GovernanceGate(FakeApprovals(), FakeSecurity(False))
    with pytest.raises(PermissionError):
        gate.decide(
            principal=principal(), request_id="approval-1",
            tenant_id="t", approve=True, reason="reviewed",
        )


def test_decide_passes_authenticated_identity():
    gate = GovernanceGate(FakeApprovals(), FakeSecurity())
    result = gate.decide(
        principal=principal(), request_id="approval-1",
        tenant_id="t", approve=True, reason="reviewed",
    )
    assert result["reviewer_id"] == "reviewer"
    assert result["authorized"] is True
