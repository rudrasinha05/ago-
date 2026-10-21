"""Local AGO LLM provider is explicitly opted in, loopback only and tool-free."""
import json

import pytest

from ago.model_handlers import optional_model_handlers
from ago.model_provider import OllamaLocalTextProvider


class Response:
    def __init__(self,data):
        self.raw=json.dumps(data).encode()
    def __enter__(self):
        return self
    def __exit__(self,*args):
        return False
    def read(self,size):
        return self.raw[:size]


def test_local_model_never_calls_an_external_domain_or_runs_tools():
    seen={}
    def opener(req,timeout):
        seen["url"]=req.full_url
        seen["body"]=json.loads(req.data)
        seen["headers"]=dict(req.headers)
        seen["timeout"]=timeout
        return Response({"done":True,"response":"Local review note"})
    provider=OllamaLocalTextProvider(model="small-local:1b",opener=opener)
    assert provider.generate("A bounded internal note")=="Local review note"
    assert seen["url"]=="http://127.0.0.1:11434/api/generate"
    assert seen["body"]["stream"] is False
    assert seen["body"]["keep_alive"]=="0s"
    assert seen["body"]["options"]["num_predict"]<=1024
    assert "tools" not in seen["body"]
    assert "Authorization" not in seen["headers"]
    assert seen["timeout"]<=60


def test_local_provider_denies_untrusted_model_names_and_noncompleted_responses():
    for model in ("","../../secret","foo/path","some model","@"*111):
        with pytest.raises(ValueError):
            OllamaLocalTextProvider(model=model)
    provider=OllamaLocalTextProvider(model="safe",opener=lambda *_args,**_kwargs:
                                   Response({"done":False,"response":"unfinished"}))
    with pytest.raises(RuntimeError):
        provider.generate("Internal notes")


def test_no_unattended_local_credential_or_paid_provider_fallback(monkeypatch):
    monkeypatch.setenv("AGO_LLM_PROVIDER","ollama_local")
    monkeypatch.setenv("AGO_LLM_MODEL","review-model:1b")
    monkeypatch.delenv("AGO_ENABLE_LOCAL_MODELS",raising=False)
    monkeypatch.setenv("AGO_ENABLE_PAID_MODELS","true")
    assert optional_model_handlers(None,None)=={}
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS","true")
    tasks=optional_model_handlers(None,None)
    assert sorted(tasks)==["project:plan","research:brief"]
    monkeypatch.setenv("AGO_LLM_PROVIDER","unknown_cloud_provider")
    assert optional_model_handlers(None,None)=={}
