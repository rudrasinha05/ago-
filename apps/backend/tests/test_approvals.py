"""M2 human approval invariant tests."""
import pytest

from ago.approvals import ApprovalRequest, ApprovalStatus


def sample():
    return ApprovalRequest.propose(
        tenant_id="tenant-a", action="deploy:production", requester_id="agent-1"
    )


def test_pending_is_not_executable():
    with pytest.raises(PermissionError):
        sample().assert_executable(tenant_id="tenant-a", action="deploy:production")


def test_independent_approval_is_scoped():
    approved = sample().decide(
        reviewer_id="human-1", tenant_id="tenant-a", approve=True, reason="Reviewed"
    )
    assert approved.status == ApprovalStatus.APPROVED
    approved.assert_executable(tenant_id="tenant-a", action="deploy:production")
    for tenant, action in [("tenant-b", "deploy:production"), ("tenant-a", "spend:100")]:
        with pytest.raises(PermissionError):
            approved.assert_executable(tenant_id=tenant, action=action)


def test_rejection_never_authorizes():
    rejected = sample().decide(
        reviewer_id="human-1", tenant_id="tenant-a", approve=False, reason="Risk"
    )
    with pytest.raises(PermissionError):
        rejected.assert_executable(tenant_id="tenant-a", action="deploy:production")


@pytest.mark.parametrize("reviewer,tenant", [("agent-1", "tenant-a"), ("human-1", "tenant-b"), ("", "tenant-a")])
def test_invalid_reviewers_or_tenants_rejected(reviewer, tenant):
    with pytest.raises(PermissionError):
        sample().decide(reviewer_id=reviewer, tenant_id=tenant, approve=True, reason="ok")


def test_decisions_are_final():
    approved = sample().decide(
        reviewer_id="human-1", tenant_id="tenant-a", approve=True, reason="ok"
    )
    with pytest.raises(ValueError):
        approved.decide(
            reviewer_id="human-2", tenant_id="tenant-a", approve=False, reason="no"
        )


def test_reason_and_proposal_required():
    with pytest.raises(ValueError):
        ApprovalRequest.propose(tenant_id="", action="deploy", requester_id="agent")
    with pytest.raises(ValueError):
        sample().decide(
            reviewer_id="human-1", tenant_id="tenant-a", approve=True, reason=" "
        )
