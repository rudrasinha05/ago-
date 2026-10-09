"""M2 governance policy tests (database integration is separately gated)."""
import pytest

from ago.governance import ApprovalRepository, Constitution, Risk


@pytest.mark.parametrize(
    "action", ["deploy:prod", "spend:100", "delete:tenant", "external:email", "unknown"]
)
def test_constitution_fails_closed(action):
    policy = Constitution()
    assert policy.classify(action) == Risk.HIGH
    assert policy.requires_approval(action)


def test_empty_action_rejected():
    with pytest.raises(ValueError):
        Constitution().classify("  ")


def test_untrusted_reviewer_denied_before_database():
    class NeverConnect:
        def transaction(self):
            raise AssertionError("Should not reach database")

    with pytest.raises(PermissionError):
        ApprovalRepository(NeverConnect()).decide(
            request_id="a", tenant_id="b", reviewer_id="c",
            approve=True, reason="ok",
        )
