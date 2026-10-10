"""M8 security tests for the fixed read-only connector and frozen tool catalog."""
import json
from uuid import uuid4

import pytest

from ago.m8_permissions import ROLE_PERMISSIONS, grant_existing_role
from ago.tool_catalog import (
    TOOL_CODES, ReadOnlyMetricsProvider, handlers, require_tool_code,
)


class FakeResponse:
    status = 200

    def __init__(self, document):
        self.payload = json.dumps(document).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self, _limit):
        return self.payload


def test_only_exact_registered_tool_actions_are_accepted():
    assert TOOL_CODES == {
        "tool:scorecard", "tool:knowledge_digest", "tool:external_metrics",
    }
    for attack in (
        "tool:shell", "spend:money", "external:post", "tool:external_metrics/../delete",
        "tool:scorecard;rm -rf", "", "TOOL:SCORECARD",
    ):
        with pytest.raises(ValueError):
            require_tool_code(attack)
    assert set(handlers(None)) == TOOL_CODES


@pytest.mark.parametrize(
    "hostname",
    ["localhost", "127.0.0.1", "localhost.local", "user@domain.com",
     "example.com:443", "http://example.com", "10.10.10.10", "intranet.internal",
     "www.example.com/path", "public.test"],
)
def test_operator_host_must_be_an_unambiguous_public_fqdn(hostname):
    with pytest.raises(ValueError):
        ReadOnlyMetricsProvider(hostname=hostname, api_token="operator-secret")


def test_external_adapter_uses_readonly_fixed_path_and_returns_numeric_only():
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        return FakeResponse({"metrics": {"jobs": 3, "load": 0.25}})
    provider = ReadOnlyMetricsProvider(
        hostname="reports.example.com", api_token="operator-secret", opener=opener,
    )
    result = provider.fetch()
    assert result == {
        "source": "operator_https_readonly",
        "metrics": {"jobs": 3, "load": 0.25},
        "untrusted_external_data": True,
    }
    request, timeout = calls[0]
    assert request.full_url == "https://reports.example.com/v1/metrics"
    assert request.get_method() == "GET"
    assert timeout <= 10
    assert request.headers["Authorization"] == "Bearer operator-secret"


@pytest.mark.parametrize(
    "data",
    [
        {"metrics": {"leaked_secret": "token"}},
        {"metrics": {"unexpected": None}},
        {"metrics": {"nested": {"private": 1}}},
        {"metrics": ["not_object"]},
        {"error": "missing_metrics"},
    ],
)
def test_external_adapter_rejects_untrusted_non_numeric_data(data):
    provider = ReadOnlyMetricsProvider(
        hostname="reports.example.com", api_token="operator-secret",
        opener=lambda request, timeout: FakeResponse(data),
    )
    with pytest.raises(ValueError):
        provider.fetch()


def test_existing_tenant_permissions_cannot_be_granted_without_operator_confirmation():
    with pytest.raises(PermissionError):
        grant_existing_role(None, tenant_id=str(uuid4()), role="founder")
    with pytest.raises(ValueError):
        grant_existing_role(
            None, tenant_id=str(uuid4()), role="all_powerful", confirmed=True,
        )
    assert "tool:dispatch" not in ROLE_PERMISSIONS["reviewer"]
    assert "tool:enroll" not in ROLE_PERMISSIONS["reviewer"]
    assert "tool:read" in ROLE_PERMISSIONS["reviewer"]
