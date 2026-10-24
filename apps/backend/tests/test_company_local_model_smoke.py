"""No fake real-model proof from mocked CI and no accidental provider calls."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    return importlib.import_module("ago_local_model_smoke")


def prepare(monkeypatch):
    monkeypatch.setenv("AGO_LLM_MODEL", "qwen2.5-coder:1.5b")
    monkeypatch.setenv("AGO_LLM_PROVIDER", "ollama_local")
    monkeypatch.setenv("AGO_ENABLE_LOCAL_MODELS", "true")


def test_read_only_preview_never_calls_ollama(tmp_path, module, monkeypatch):
    prepare(monkeypatch)
    calls = []
    output = tmp_path / "receipt.json"
    fake = SimpleNamespace(generate=lambda p: calls.append(p) or "Two")
    info = module.smoke(output, provider=fake)
    assert info["status"] == "inspection_only"
    assert info["provider_called"] is False
    assert info["real_local_inference_proved"] is False
    assert info["real_founder_project_executed"] is False
    assert calls == [] and not output.exists()


def test_one_consent_uses_bounded_local_prompt_without_raw_model_output(
        tmp_path, module, monkeypatch):
    prepare(monkeypatch)
    out = tmp_path / "receipt.json"
    calls = []
    raw = "PRIVATE_LOCAL_RESPONSE_TEST_VALUE"
    provider = SimpleNamespace(generate=lambda p: calls.append(p) or raw)
    tick = iter([1.0, 1.25])
    result = module.smoke(out, apply=True, confirm=module.CONFIRM,
                          provider=provider, clock=lambda: next(tick))
    assert len(calls) == 1
    assert len(calls[0]) < 4000
    assert result["provider_called"] is True
    assert result["real_local_inference_proved"] is False
    assert result["elapsed_seconds"] == 0.25
    assert result["independent_human_qa_approved"] is False
    assert result["github_committed"] is False
    assert result["release_ready"] is False
    saved = out.read_text(encoding="utf-8")
    assert raw not in saved
    assert json.loads(saved) == result
    with pytest.raises(FileExistsError):
        module.smoke(out, apply=True, confirm=module.CONFIRM,
                     provider=provider)
    assert len(calls) == 1


def test_missing_consent_invalid_environment_never_calls_local_model(
        tmp_path, module, monkeypatch):
    prepare(monkeypatch)
    calls = []
    provider = SimpleNamespace(generate=lambda prompt: calls.append(prompt) or "2")
    out = tmp_path / "receipt.json"
    with pytest.raises(PermissionError, match="consent"):
        module.smoke(out, apply=True, provider=provider)
    for flag in ("AGO_LLM_PROVIDER", "AGO_ENABLE_LOCAL_MODELS"):
        prepare(monkeypatch)
        monkeypatch.delenv(flag)
        with pytest.raises(PermissionError, match="local-only"):
            module.smoke(out, apply=True, confirm=module.CONFIRM,
                         provider=provider)
    assert calls == [] and not out.exists()


def test_no_model_no_proof_and_failed_inference_cannot_write(
        tmp_path, module, monkeypatch):
    prepare(monkeypatch)
    out = tmp_path / "out.json"
    monkeypatch.delenv("AGO_LLM_MODEL")
    with pytest.raises(ValueError, match="installed"):
        module.smoke(out)
    prepare(monkeypatch)
    def broken(_prompt):
        raise RuntimeError("no model available")
    with pytest.raises(RuntimeError):
        module.smoke(out, apply=True, confirm=module.CONFIRM,
                     provider=SimpleNamespace(generate=broken))
    assert not out.exists()
