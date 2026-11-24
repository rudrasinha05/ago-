"""AI-001: the Founder's cloud model settings API, against real PostgreSQL auth.

Cloud calls go to a fake opener; no network, no real key, no cost.
"""
import io
import json

import pytest

import ago.api_company_chat as api_company_chat
from ago.model_provider import ProviderVault
from test_m7_http_postgres import case as case  # noqa: F401

KEY = "gsk-test-key-0123456789wxyz"
BASE = "/v1/organization/company"


class FakeOpener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        if request.get_method() == "GET":
            return io.BytesIO(json.dumps({"data": [{"id": "model-b"}, {"id": "model-a"}]}).encode())
        return io.BytesIO(json.dumps({
            "choices": [{"finish_reason": "stop", "message": {"content": "OK"}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 1}}).encode())


@pytest.fixture
def vault(tmp_path, monkeypatch):
    opener = FakeOpener()
    monkeypatch.setattr(api_company_chat, "ProviderVault", lambda: ProviderVault(tmp_path, opener=opener))
    return tmp_path, opener


def test_founder_saves_tests_routes_and_removes_a_key_that_is_never_returned(case, vault):
    client, headers, _ = case
    founder = headers["founder"]
    folder, opener = vault
    view = client.get(BASE + "/cloud-models", headers=founder).json()
    assert view["available"] is True and [p["provider"] for p in view["providers"]] == [
        "openai", "anthropic", "gemini", "groq"]
    assert not any(p["saved"] for p in view["providers"])

    saved = client.put(BASE + "/cloud-models/groq", headers=founder,
                       json={"model": "model-a", "api_key": KEY})
    assert saved.status_code == 200 and KEY not in saved.text
    groq = next(p for p in saved.json()["providers"] if p["provider"] == "groq")
    assert groq["key_hint"] == "…wxyz" and groq["model"] == "model-a"
    assert KEY not in (folder / "model_providers.json").read_text()

    models = client.get(BASE + "/cloud-models/groq/models", headers=founder).json()
    assert models == {"provider": "groq", "models": ["model-a", "model-b"]}

    untested = client.put(BASE + "/cloud-model-routes", headers=founder,
                          json={"code": "groq", "monthly_call_cap": 20})
    assert untested.status_code == 422 and "Test" in untested.json()["detail"]

    tested = client.post(BASE + "/cloud-models/groq/test", headers=founder).json()
    assert tested["test"] == {"provider": "groq", "ok": True, "code": None}
    routed = client.put(BASE + "/cloud-model-routes", headers=founder,
                        json={"code": "groq", "qa": None, "chat": "groq", "monthly_call_cap": 20}).json()
    assert routed["routes"] == {"code": "groq", "qa": None, "chat": "groq"}
    assert routed["monthly_call_cap"] == 20 and routed["usage"]["calls"] == 1
    sent = [r for r in opener.requests if r.get_method() == "POST"]
    assert len(sent) == 1 and KEY not in (sent[0].data or b"").decode()

    removed = client.delete(BASE + "/cloud-models/groq", headers=founder).json()
    assert removed["routes"] == {"code": None, "qa": None, "chat": None}
    assert not any(p["saved"] for p in removed["providers"])


def test_only_the_founder_can_see_or_change_cloud_models_and_inputs_are_checked(case, vault):
    client, headers, _ = case
    reviewer, founder = headers["reviewer"], headers["founder"]
    assert client.get(BASE + "/cloud-models").status_code == 401
    assert client.get(BASE + "/cloud-models", headers=reviewer).status_code == 403
    assert client.put(BASE + "/cloud-models/groq", headers=reviewer,
                      json={"model": "m", "api_key": KEY}).status_code == 403
    assert client.put(BASE + "/cloud-models/other", headers=founder,
                      json={"model": "m", "api_key": KEY}).status_code == 404
    assert client.put(BASE + "/cloud-models/groq", headers=founder,
                      json={"model": "m", "api_key": KEY, "extra": 1}).status_code == 422
    assert client.put(BASE + "/cloud-models/groq", headers=founder,
                      json={"model": "bad name", "api_key": KEY}).status_code == 422
    assert client.put(BASE + "/cloud-models/groq", headers=founder,
                      json={"model": "m"}).status_code == 422          # first save needs a key
    assert client.post(BASE + "/cloud-models/groq/test", headers=founder).status_code == 404
    assert client.put(BASE + "/cloud-model-routes", headers=founder,
                      json={"code": None, "monthly_call_cap": 99999}).status_code == 422


def test_keys_cannot_be_entered_on_a_production_server(case, vault, monkeypatch):
    client, headers, _ = case
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    founder = headers["founder"]
    assert client.put(BASE + "/cloud-models/groq", headers=founder,
                      json={"model": "m", "api_key": KEY}).status_code == 409


def test_founder_connects_with_only_a_key(case, vault):
    client, headers, _ = case
    founder = headers["founder"]
    assert client.post(BASE + "/cloud-models/groq/connect", headers=headers["reviewer"],
                       json={"api_key": KEY}).status_code == 403
    assert client.post(BASE + "/cloud-models/groq/connect", headers=founder,
                       json={"api_key": KEY, "model": "x"}).status_code == 422
    result = client.post(BASE + "/cloud-models/groq/connect", headers=founder, json={"api_key": KEY})
    assert result.status_code == 200 and KEY not in result.text
    body = result.json()
    assert body["connect"]["ok"] is True and body["connect"]["model"] == "model-a"
    assert body["routes"]["code"] == "groq"
    switched = client.put(BASE + "/cloud-models/groq/model", headers=founder, json={"model": "model-b"}).json()
    assert switched["test"]["ok"] is True
    assert next(p for p in switched["providers"] if p["provider"] == "groq")["model"] == "model-b"
    assert client.put(BASE + "/cloud-models/openai/model", headers=founder,
                      json={"model": "m"}).status_code == 422          # not connected yet
