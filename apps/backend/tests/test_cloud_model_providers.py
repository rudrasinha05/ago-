"""AI-001: Founder-activated cloud models (OpenAI, Claude, Gemini, Groq).

Every call here goes to a fake HTTP opener: no network, no real key, no cost.
"""
import io
import json
from urllib.error import HTTPError, URLError

import pytest

from ago.model_provider import (
    CloudCapReached, CloudProviderError, CloudTextProvider, FallbackProvider,
    ProviderVault,
)

KEY = "sk-test-0123456789abcd"
TENANT = "10000000-0000-4000-8000-000000000001"


class FakeOpener:
    """Records requests; answers with queued JSON bodies or exceptions."""

    def __init__(self, *answers):
        self.answers = list(answers)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return io.BytesIO(json.dumps(answer).encode())


def body(request):
    return json.loads(request.data) if request.data else None


ANSWERS = {
    "openai": {"status": "completed", "usage": {"input_tokens": 11, "output_tokens": 3},
               "output": [{"type": "message", "content": [{"type": "output_text", "text": "OK"}]}]},
    "anthropic": {"stop_reason": "end_turn", "usage": {"input_tokens": 11, "output_tokens": 3},
                  "content": [{"type": "text", "text": "OK"}]},
    "gemini": {"candidates": [{"finishReason": "STOP", "content": {"parts": [
        {"text": "thinking...", "thought": True}, {"text": "OK"}]}}],
        "usageMetadata": {"promptTokenCount": 11, "candidatesTokenCount": 3}},
    "groq": {"choices": [{"finish_reason": "stop", "message": {"content": "OK"}}],
             "usage": {"prompt_tokens": 11, "completion_tokens": 3}},
}
ENDPOINTS = {
    "openai": "https://api.openai.com/v1/responses",
    "anthropic": "https://api.anthropic.com/v1/messages",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/models/m-1:generateContent",
    "groq": "https://api.groq.com/openai/v1/chat/completions",
}


@pytest.mark.parametrize("name", sorted(ANSWERS))
def test_each_provider_sends_one_bounded_call_and_reads_answer_and_usage(name):
    opener = FakeOpener(ANSWERS[name])
    provider = CloudTextProvider(provider=name, api_key=KEY, model="m-1", opener=opener)
    assert provider.generate("Say OK") == "OK"          # Gemini thought parts are dropped
    assert provider.last_usage == (11, 3)
    request = opener.requests[0]
    assert request.full_url == ENDPOINTS[name] and request.get_method() == "POST"
    headers = {k.lower(): v for k, v in request.header_items()}
    secret = {"anthropic": "x-api-key", "gemini": "x-goog-api-key"}.get(name, "authorization")
    assert KEY in headers[secret]
    assert KEY not in json.dumps(body(request))          # the key never goes in the body
    assert "tools" not in body(request) and "Say OK" in json.dumps(body(request))


def test_code_answers_ask_for_json_where_the_provider_supports_it():
    schema = {"type": "object", "properties": {"files": {"type": "array"}}}
    for name, check in {
        "openai": lambda b: b["text"]["format"]["type"] == "json_object",
        "groq": lambda b: b["response_format"]["type"] == "json_object",
        "gemini": lambda b: b["generationConfig"]["responseMimeType"] == "application/json",
        "anthropic": lambda b: "JSON Schema" in b["messages"][0]["content"],
    }.items():
        opener = FakeOpener(ANSWERS[name])
        CloudTextProvider(provider=name, api_key=KEY, model="m-1", opener=opener).generate(
            "Write code", response_schema=schema)
        assert check(body(opener.requests[0])), name


@pytest.mark.parametrize("error,code", [
    (HTTPError("u", 401, "x", {}, None), "auth_failed"),
    (HTTPError("u", 404, "x", {}, None), "model_not_found"),
    (HTTPError("u", 429, "x", {}, None), "rate_limited_or_no_credit"),
    (HTTPError("u", 503, "x", {}, None), "provider_unavailable"),
    (URLError("no route"), "network_unreachable"),
])
def test_failures_become_agos_own_words_never_provider_text(error, code):
    provider = CloudTextProvider(provider="openai", api_key=KEY, model="m", opener=FakeOpener(error))
    with pytest.raises(CloudProviderError) as raised:
        provider.generate("hi")
    assert raised.value.code == code and KEY not in str(raised.value)


def test_cut_off_or_empty_answers_are_not_accepted():
    for name, answer in {
        "openai": {"status": "incomplete", "output": []},
        "anthropic": {"stop_reason": "max_tokens", "content": [{"type": "text", "text": "half"}]},
        "gemini": {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": []}}]},
        "groq": {"choices": [{"finish_reason": "length", "message": {"content": "half"}}]},
    }.items():
        provider = CloudTextProvider(provider=name, api_key=KEY, model="m", opener=FakeOpener(answer))
        with pytest.raises(CloudProviderError):
            provider.generate("hi")


def test_bad_names_and_keys_are_refused_before_any_call():
    for bad in ("", "a b", "x" * 130, "../etc", "m;rm"):
        with pytest.raises(ValueError):
            CloudTextProvider(provider="groq", api_key=KEY, model=bad)
    with pytest.raises(ValueError):
        CloudTextProvider(provider="groq", api_key="short", model="m")
    with pytest.raises(ValueError):
        CloudTextProvider(provider="other", api_key=KEY, model="m")


def test_model_lists_are_read_only_gets():
    opener = FakeOpener({"models": [
        {"name": "models/gemini-a", "supportedGenerationMethods": ["generateContent"]},
        {"name": "models/embed-b", "supportedGenerationMethods": ["embedContent"]}]})
    names = CloudTextProvider(provider="gemini", api_key=KEY, model="m", opener=opener).list_models()
    assert names == ["gemini-a"] and opener.requests[0].get_method() == "GET"
    opener = FakeOpener({"data": [{"id": "b"}, {"id": "a"}, {"id": "bad name"}]})
    assert CloudTextProvider(provider="openai", api_key=KEY, model="m", opener=opener).list_models() == ["a", "b"]


def test_vault_keeps_keys_encrypted_write_only_and_tested_before_use(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["anthropic"])
    vault = ProviderVault(tmp_path, opener=opener)
    view = vault.save(TENANT, "anthropic", model="claude-x", api_key=KEY)
    entry = next(p for p in view["providers"] if p["provider"] == "anthropic")
    assert entry["saved"] and entry["key_hint"] == "…abcd" and entry["test_status"] is None
    stored = (tmp_path / "model_providers.json").read_text()
    assert KEY not in stored and KEY not in json.dumps(view)
    with pytest.raises(ValueError, match="Test"):
        vault.set_routes(TENANT, {"code": "anthropic"}, 10)   # untested key cannot do work
    assert vault.for_route(TENANT, "code") is None
    tested = vault.test(TENANT, "anthropic")
    assert tested["test"] == {"provider": "anthropic", "ok": True, "code": None}
    vault.set_routes(TENANT, {"code": "anthropic", "qa": None, "chat": None}, 10)
    assert vault.for_route(TENANT, "code").label == "anthropic:claude-x"
    assert vault.for_route(TENANT, "qa") is None
    assert vault.view(TENANT)["usage"]["calls"] == 1      # the test call counted
    # A new key or model must be tested again; its routes are cleared.
    vault.save(TENANT, "anthropic", model="claude-y", api_key=None)
    assert vault.view(TENANT)["routes"]["code"] is None
    # Other organizations see nothing.
    other = vault.view("20000000-0000-4000-8000-000000000002")
    assert not any(p["saved"] for p in other["providers"])
    vault.remove(TENANT, "anthropic")
    assert not any(p["saved"] for p in vault.view(TENANT)["providers"])


def test_monthly_cap_stops_cloud_calls_and_local_model_takes_over(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["groq"], ANSWERS["groq"], ANSWERS["groq"])
    vault = ProviderVault(tmp_path, opener=opener)
    vault.save(TENANT, "groq", model="g-1", api_key=KEY)
    vault.test(TENANT, "groq")
    vault.set_routes(TENANT, {"code": "groq"}, 2)

    class Local:
        supports_response_schema = True
        calls = 0

        def generate(self, prompt, **options):
            Local.calls += 1
            return "local answer"

    chained = FallbackProvider(vault.for_route(TENANT, "code"), Local(), fallback_label="ollama:qwen3:4b")
    assert chained.generate("first") == "OK" and chained.label == "groq:g-1"
    assert chained.generate("second") == "local answer"      # cap of 2 reached (test + 1)
    assert chained.label == "ollama:qwen3:4b" and chained.cloud_failures == ["monthly_cap_reached"]
    usage = vault.view(TENANT)["usage"]
    assert usage["calls"] == 2 and usage["input_tokens"] == 22 and usage["by_provider"]["groq"]["calls"] == 2
    with pytest.raises(CloudCapReached):
        vault.metered(TENANT, "groq").generate("third")


def test_cloud_failure_falls_back_and_is_recorded_for_the_founder(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["openai"], HTTPError("u", 401, "x", {}, None))
    vault = ProviderVault(tmp_path, opener=opener)
    vault.save(TENANT, "openai", model="o-1", api_key=KEY)
    vault.test(TENANT, "openai")
    vault.set_routes(TENANT, {"qa": "openai"}, 50)

    class Local:
        def generate(self, prompt, **options):
            assert "response_schema" not in options             # local cannot take a schema
            return "QA_VERDICT: PASS"

    chained = FallbackProvider(vault.for_route(TENANT, "qa"), Local(), fallback_label="ollama:q")
    assert chained.generate("review", response_schema={"type": "object"}) == "QA_VERDICT: PASS"
    entry = next(p for p in vault.view(TENANT)["providers"] if p["provider"] == "openai")
    assert entry["last_error"] == "auth_failed"


def test_cloud_models_stay_off_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    vault = ProviderVault(tmp_path, opener=FakeOpener(ANSWERS["groq"]))
    vault.save(TENANT, "groq", model="g", api_key=KEY)
    vault.test(TENANT, "groq")
    vault.set_routes(TENANT, {"chat": "groq"}, 5)
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    assert vault.for_route(TENANT, "chat") is None
    assert vault.view(TENANT)["available"] is False
