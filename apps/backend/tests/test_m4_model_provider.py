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


def test_provider_never_forwards_credentials_through_proxy_or_redirect(monkeypatch):
    from urllib.request import HTTPRedirectHandler, ProxyHandler, Request

    monkeypatch.setenv('HTTPS_PROXY', 'http://untrusted.example:8080')
    monkeypatch.setenv('https_proxy', 'http://untrusted.example:8080')
    provider = ResponsesTextProvider(api_key='test-key', model='configured-model')
    handlers = provider.opener.__self__.handlers
    assert not any(h.proxies for h in handlers if isinstance(h, ProxyHandler))
    redirect = next(h for h in handlers if isinstance(h, HTTPRedirectHandler))
    request = Request(provider.ENDPOINT, data=b'private prompt',
                      headers={'Authorization': 'Bearer test-key'})
    for code in (301, 302, 303, 307, 308):
        with pytest.raises(RuntimeError, match='never redirect'):
            redirect.redirect_request(request, None, code, 'redirect', {},
                                      'https://untrusted.example/collect')
