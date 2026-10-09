"""M4 Responses provider is bounded, tool-free and opt-in."""
import json

import pytest

from ago.model_handlers import optional_model_handlers
from ago.model_provider import ResponsesTextProvider


class FakeHTTP:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, _size):
        return self.payload


def test_provider_sends_no_tools_and_no_persistent_storage():
    observed = {}
    def opener(request, timeout):
        observed["timeout"] = timeout
        observed["body"] = json.loads(request.data)
        observed["url"] = request.full_url
        return FakeHTTP({
            "status": "completed",
            "output": [{"type": "message", "content": [
                {"type": "output_text", "text": "Internal result"},
            ]}],
        })
    adapter = ResponsesTextProvider(
        api_key="test-key", model="configured-model", opener=opener,
    )
    assert adapter.generate("Draft a brief") == "Internal result"
    assert observed["body"]["store"] is False
    assert "tools" not in observed["body"]
    assert observed["body"]["max_output_tokens"] <= 1024
    assert observed["url"].endswith("/v1/responses")


def test_paid_provider_is_off_by_default(monkeypatch):
    monkeypatch.delenv("AGO_ENABLE_PAID_MODELS", raising=False)
    monkeypatch.setenv("AGO_LLM_API_KEY", "test-key")
    monkeypatch.setenv("AGO_LLM_MODEL", "test-model")
    assert optional_model_handlers(None, None) == {}


def test_invalid_model_or_prompt_fail_closed():
    with pytest.raises(ValueError):
        ResponsesTextProvider(api_key="", model="model")
    provider = ResponsesTextProvider(api_key="test", model="model")
    with pytest.raises(ValueError):
        provider.generate("")
