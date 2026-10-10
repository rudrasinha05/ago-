"""M6 existing-tenant role grants require explicit local operator confirmation."""
from uuid import uuid4

import pytest

from ago.m6_permissions import ROLE_PERMISSIONS, grant_existing_role


def test_role_upgrade_fails_closed_without_consent():
    tenant = str(uuid4())
    with pytest.raises(PermissionError):
        grant_existing_role(None, tenant_id=tenant, role="founder")
    with pytest.raises(ValueError):
        grant_existing_role(None, tenant_id=tenant, role="superadmin", confirmed=True)


def test_reviewer_role_cannot_propose_or_finalize_council():
    reviewer = ROLE_PERMISSIONS["reviewer"]
    assert "council:vote" in reviewer
    assert "council:propose" not in reviewer
    assert "council:finalize" not in reviewer


def test_founder_upgrade_contains_explicit_permissions():
    founder = ROLE_PERMISSIONS["founder"]
    assert "knowledge:read" in founder
    assert "operations:request" in founder
    assert len(founder) == len(set(founder))
