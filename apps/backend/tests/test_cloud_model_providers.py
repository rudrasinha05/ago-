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
    assert headers["user-agent"].startswith("AGO/")       # never Python's default agent


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
    (HTTPError("u", 403, "x", {}, None), "access_denied"),
    (HTTPError("u", 404, "x", {}, None), "model_not_found"),
    (HTTPError("u", 429, "x", {}, None), "rate_limited_or_no_credit"),
    (HTTPError("u", 503, "x", {}, None), "provider_unavailable"),
    (URLError("no route"), "network_unreachable"),
])
def test_failures_become_agos_own_words_never_provider_text(error, code):
    # A 5xx gets one retry; give the fake the same failure twice.
    provider = CloudTextProvider(provider="openai", api_key=KEY, model="m",
                                 opener=FakeOpener(error, error), sleep=lambda s: None)
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


def test_vault_keeps_keys_encrypted_write_only_and_only_tested_models_reach_the_manager(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["anthropic"])
    vault = ProviderVault(tmp_path, opener=opener)
    view = vault.save(TENANT, "anthropic", model="claude-x", api_key=KEY)
    entry = next(p for p in view["providers"] if p["provider"] == "anthropic")
    assert entry["saved"] and entry["key_hint"] == "…abcd" and entry["test_status"] is None
    stored = (tmp_path / "model_providers.json").read_text()
    assert KEY not in stored and KEY not in json.dumps(view)
    assert vault.policy(TENANT)["models"] == []                      # untested key does no work
    tested = vault.test(TENANT, "anthropic")
    assert tested["test"] == {"provider": "anthropic", "ok": True, "code": None}
    assert vault.policy(TENANT) == {"allow_paid": True, "paid_cap_reached": False,
                                    "models": [{"provider": "anthropic", "model": "claude-x"}]}
    usage = vault.view(TENANT)["usage"]
    assert usage["calls"] == 1 and usage["paid_calls"] == 1           # Claude is paid
    # A new key or model must pass a test again before the Manager may use it.
    vault.save(TENANT, "anthropic", model="claude-y", api_key=None)
    assert vault.policy(TENANT)["models"] == []
    other = vault.view("20000000-0000-4000-8000-000000000002")
    assert not any(p["saved"] for p in other["providers"])
    vault.remove(TENANT, "anthropic")
    assert not any(p["saved"] for p in vault.view(TENANT)["providers"])


def test_the_monthly_limit_counts_paid_calls_only_and_the_founder_can_forbid_paid(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["groq"], ANSWERS["openai"], ANSWERS["groq"], ANSWERS["groq"],
                        ANSWERS["groq"], ANSWERS["openai"])
    vault = ProviderVault(tmp_path, opener=opener)
    for name, model in (("groq", "g-1"), ("openai", "o-1")):
        vault.save(TENANT, name, model=model, api_key=KEY)
    vault.set_policy(TENANT, allow_paid=True, monthly_call_cap=2)
    vault.test(TENANT, "groq")
    vault.test(TENANT, "openai")                                       # paid call 1 of 2
    for _ in range(3):
        vault.metered(TENANT, "groq").generate("free work")            # free calls never hit the limit
    vault.metered(TENANT, "openai").generate("paid work")              # paid call 2 of 2

    class Local:
        supports_response_schema = True

        def generate(self, prompt, **options):
            return "local answer"

    chained = FallbackProvider(vault.metered(TENANT, "openai"), Local(), fallback_label="ollama:qwen3:4b")
    assert chained.generate("third paid") == "local answer"
    assert chained.label == "ollama:qwen3:4b" and chained.cloud_failures == ["monthly_cap_reached"]
    usage = vault.view(TENANT)["usage"]
    assert usage["calls"] == 6 and usage["paid_calls"] == 2 and usage["by_provider"]["groq"]["calls"] == 4
    assert vault.policy(TENANT)["paid_cap_reached"] is True
    vault.set_policy(TENANT, allow_paid=False, monthly_call_cap=500)
    with pytest.raises(CloudCapReached):
        vault.metered(TENANT, "openai").generate("not allowed")
    with pytest.raises(ValueError):
        vault.set_policy(TENANT, allow_paid=True, monthly_call_cap=-1)


def test_cloud_failure_falls_back_and_is_recorded_for_the_founder(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["openai"], HTTPError("u", 401, "x", {}, None))
    vault = ProviderVault(tmp_path, opener=opener)
    vault.save(TENANT, "openai", model="o-1", api_key=KEY)
    vault.test(TENANT, "openai")

    class Local:
        def generate(self, prompt, **options):
            assert "response_schema" not in options             # local cannot take a schema
            return "QA_VERDICT: PASS"

    chained = FallbackProvider(vault.metered(TENANT, "openai"), Local(), fallback_label="ollama:q")
    assert chained.generate("review", response_schema={"type": "object"}) == "QA_VERDICT: PASS"
    entry = next(p for p in vault.view(TENANT)["providers"] if p["provider"] == "openai")
    assert entry["last_error"] == "auth_failed"


def test_cloud_models_stay_off_in_production(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    assert ProviderVault(tmp_path).view(TENANT)["available"] is False


def test_agos_code_model_choice_is_a_strong_text_model_from_the_keys_own_list():
    from ago.model_provider import choose_code_model
    assert choose_code_model("anthropic", ["claude-haiku-5-5", "claude-opus-5-5", "claude-sonnet-5-5",
                                           "claude-sonnet-4-6"]) == "claude-sonnet-5-5"
    assert choose_code_model("openai", ["gpt-6.2-astra", "gpt-6.2-sol", "gpt-6.1-sol", "gpt-6-luna",
                                        "whisper-1", "text-embedding-3", "gpt-image-1"]) == "gpt-6.2-sol"
    assert choose_code_model("gemini", ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.5-flash-lite",
                                        "gemini-3.1-pro-preview", "gemini-embedding-001"]) == "gemini-3.8-flash"
    assert choose_code_model("groq", ["llama-3.1-8b-instant", "openai/gpt-oss-120b", "whisper-large-v3"]) \
        == "openai/gpt-oss-120b"
    assert choose_code_model("groq", ["whisper-large-v3"]) is None


def test_connect_with_only_a_key_picks_and_tests_a_model(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    listing = {"models": [{"name": "models/gemini-3.8-flash", "supportedGenerationMethods": ["generateContent"]},
                          {"name": "models/gemini-3.5-flash-lite", "supportedGenerationMethods": ["generateContent"]}]}
    opener = FakeOpener(listing, ANSWERS["gemini"])
    vault = ProviderVault(tmp_path, opener=opener, sleep=lambda s: None)
    result = vault.connect(TENANT, "gemini", KEY)
    assert result["connect"] == {"provider": "gemini", "ok": True, "code": None, "saved": True,
                                 "model": "gemini-3.8-flash",
                                 "tried": [{"model": "gemini-3.8-flash", "ok": True, "code": None}]}
    assert [r.get_method() for r in opener.requests] == ["GET", "POST"]   # list, then one test call
    gemini = next(p for p in result["providers"] if p["provider"] == "gemini")
    assert gemini["test_status"] == "ok" and gemini["models"] == ["gemini-3.5-flash-lite", "gemini-3.8-flash"]
    assert vault.policy(TENANT)["models"] == [{"provider": "gemini", "model": "gemini-3.8-flash"}]
    assert KEY not in (tmp_path / "model_providers.json").read_text()
    # Switching model keeps the list and tests again.
    opener.answers.append(ANSWERS["gemini"])
    switched = vault.choose_model(TENANT, "gemini", "gemini-3.5-flash-lite")
    assert switched["test"]["ok"] is True
    entry = next(p for p in switched["providers"] if p["provider"] == "gemini")
    assert entry["model"] == "gemini-3.5-flash-lite" and len(entry["models"]) == 2


def test_a_refused_key_is_not_saved(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    vault = ProviderVault(tmp_path, opener=FakeOpener(HTTPError("u", 401, "x", {}, None)))
    result = vault.connect(TENANT, "anthropic", KEY)
    assert result["connect"] == {"provider": "anthropic", "ok": False, "code": "auth_failed", "saved": False}
    assert not any(p["saved"] for p in result["providers"])


def test_a_busy_provider_gets_one_retry_then_success():
    waits = []
    opener = FakeOpener(HTTPError("u", 503, "x", {}, None), ANSWERS["gemini"])
    provider = CloudTextProvider(provider="gemini", api_key=KEY, model="m", opener=opener,
                                 sleep=waits.append)
    assert provider.generate("hi") == "OK" and waits == [2.0] and len(opener.requests) == 2
    # 429 (limit or no credit) is not retried: it would only spend more.
    opener = FakeOpener(HTTPError("u", 429, "x", {}, None))
    with pytest.raises(CloudProviderError):
        CloudTextProvider(provider="groq", api_key=KEY, model="m", opener=opener,
                          sleep=waits.append).generate("hi")
    assert len(opener.requests) == 1


def test_claude_workspace_keys_send_the_workspace_and_say_when_one_is_missing(tmp_path, monkeypatch):
    opener = FakeOpener(ANSWERS["anthropic"])
    CloudTextProvider(provider="anthropic", api_key=KEY, model="c", opener=opener,
                      workspace_id="wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ").generate("hi")
    headers = {k.lower(): v for k, v in opener.requests[0].header_items()}
    assert headers["anthropic-workspace-id"] == "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ"
    with pytest.raises(ValueError):
        CloudTextProvider(provider="anthropic", api_key=KEY, model="c", workspace_id="org-123")
    body = io.BytesIO(b'{"error":{"message":"This API key is not scoped to a workspace, so this request '
                      b'must include the anthropic-workspace-id header"}}')
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    vault = ProviderVault(tmp_path, opener=FakeOpener(HTTPError("u", 400, "x", {}, body)))
    result = vault.connect(TENANT, "anthropic", KEY)
    assert result["connect"] == {"provider": "anthropic", "ok": False, "code": "workspace_id_needed",
                                 "saved": False}
    # With the workspace ID the key connects and keeps sending it.
    opener = FakeOpener({"data": [{"id": "claude-sonnet-5-5"}]}, ANSWERS["anthropic"], ANSWERS["anthropic"])
    vault = ProviderVault(tmp_path, opener=opener)
    result = vault.connect(TENANT, "anthropic", KEY, workspace_id="wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ")
    assert result["connect"]["ok"] is True
    assert next(p for p in result["providers"] if p["provider"] == "anthropic")["workspace_id"] \
        == "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ"
    vault.metered(TENANT, "anthropic").generate("again")
    assert all({k.lower(): v for k, v in r.header_items()}["anthropic-workspace-id"]
               == "wrkspc_01JwQvzr7rXLA5AGx3HKfFUJ" for r in opener.requests)


def test_connect_tries_the_next_model_when_one_is_busy(tmp_path, monkeypatch):
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    listing = {"models": [{"name": "models/" + n, "supportedGenerationMethods": ["generateContent"]}
                          for n in ("gemini-3.8-flash", "gemini-3.7-flash", "gemini-2.5-flash")]}
    busy = HTTPError("u", 503, "x", {}, None)
    opener = FakeOpener(listing, busy, busy, ANSWERS["gemini"])
    vault = ProviderVault(tmp_path, opener=opener, sleep=lambda s: None)
    result = vault.connect(TENANT, "gemini", KEY)
    assert result["connect"]["ok"] is True and result["connect"]["model"] == "gemini-2.5-flash"
    assert result["connect"]["tried"] == [
        {"model": "gemini-3.8-flash", "ok": False, "code": "provider_unavailable"},
        {"model": "gemini-2.5-flash", "ok": True, "code": None}]
    # A refused key is not retried with other models.
    opener = FakeOpener(listing, HTTPError("u", 401, "x", {}, None))
    other = ProviderVault(tmp_path / "b", opener=opener, sleep=lambda s: None).connect(TENANT, "gemini", KEY)
    assert other["connect"]["tried"] == [{"model": "gemini-3.8-flash", "ok": False, "code": "auth_failed"}]


def test_short_work_asks_the_cloud_model_for_a_short_answer(tmp_path, monkeypatch):
    """Live run 2026-11-25: a 4096-token Board answer was slow and AGO keeps only
    950 characters of it. The Manager now sets the answer length per kind of work."""
    import json as _json
    from ago.model_manager import OUTPUT_TOKENS
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    opener = FakeOpener(ANSWERS["openai"], ANSWERS["openai"])
    vault = ProviderVault(tmp_path, opener=opener)
    vault.save(TENANT, "openai", model="o-1", api_key=KEY)
    assert vault.metered(TENANT, "openai").inner.max_output_tokens == 4096
    board = vault.metered(TENANT, "openai", max_output_tokens=OUTPUT_TOKENS["board"])
    board.generate("vote")
    sent = _json.loads(opener.requests[-1].data)
    assert sent["max_output_tokens"] == 1200
    assert vault.metered(TENANT, "openai", max_output_tokens=10).inner.max_output_tokens == 256
    assert vault.metered(TENANT, "openai", max_output_tokens=99999).inner.max_output_tokens == 4096
    assert OUTPUT_TOKENS["code"] == 4096 and OUTPUT_TOKENS["board"] < OUTPUT_TOKENS["plan"] < OUTPUT_TOKENS["code"]
