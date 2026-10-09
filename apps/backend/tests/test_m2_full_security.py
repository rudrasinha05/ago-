"""Additional authorization and immutable QA contract tests."""
import pytest

from ago.approvals import ApprovalRequest
from ago.bootstrap import FOUNDER_PERMISSIONS
from ago.governance import Constitution
from ago.quality import Review, Verdict


def test_founder_must_still_get_independent_approval():
    assert "approval:decide" in FOUNDER_PERMISSIONS
    req = ApprovalRequest.propose(
        tenant_id="tenant", action="spend:large", requester_id="founder"
    )
    with pytest.raises(PermissionError):
        req.decide(
            reviewer_id="founder", tenant_id="tenant",
            approve=True, reason="self approval forbidden",
        )


def test_unknown_actions_are_conservatively_blocked():
    assert Constitution().requires_approval("experimental:new-operation")


def test_failed_qa_does_not_pass():
    review = Review(
        tenant_id="tenant", artifact_id="artifact",
        author_id="agent", reviewer_id="human",
        verdict=Verdict.FAIL, evidence="failed checks",
    )
    with pytest.raises(PermissionError):
        review.assert_accepted(tenant_id="tenant", artifact_id="artifact")
