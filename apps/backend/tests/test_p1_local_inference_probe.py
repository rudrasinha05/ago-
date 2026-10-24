"""Offline tests for P1 founder-only live Ollama inference verification."""
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "p1_founder_local_probe", ROOT / "scripts" / "ago_p1_local_inference_probe.py"
)
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)


class Response(io.BytesIO):
    status = 200


def test_local_model_probe_is_loopback_one_call_no_secrets_and_no_execution_grants():
    requests = []
    moments = iter([10.0, 10.4])

    def opener(request, timeout):
        requests.append((request, timeout))
        return Response(json.dumps({
            "model": "qwen2.5-coder:1.5b", "done": True, "response": "READY",
            "eval_count": 2, "eval_duration": 1234567,
        }).encode())

    result = probe.probe(
        "qwen2.5-coder:1.5b", opener=opener, clock=lambda: next(moments)
    )
    assert len(requests) == 1
    request, timeout = requests[0]
    assert request.full_url == "http://127.0.0.1:11434/api/generate"
    assert request.get_method() == "POST" and timeout == 60
    payload = json.loads(request.data)
    assert payload["stream"] is False
    assert payload["keep_alive"] == "0s"
    assert payload["options"]["num_predict"] == 16
    assert "password" not in json.dumps(payload)
    assert result["verified_live_inference"] is True
    assert result["hardware_verified"] is False
    assert result["response_text_persisted"] is False
    assert result["independent_qa_completed"] is False
    assert result["elapsed_ms"] == 400
    assert "READY" not in str(result)


@pytest.mark.parametrize("model", [
    "", " model", "http://example.com", "../local", "qwen tag",
    "a" * 101, "not%valid",
])
def test_local_probe_rejects_untrusted_model_tags_without_network(model):
    with pytest.raises(ValueError):
        probe.probe(model, opener=lambda *_a, **_k: pytest.fail("unexpected network"))


def test_local_probe_does_not_accept_model_mismatch_or_incomplete_inference():
    for item in (
        {"model": "other", "done": True, "response": "READY"},
        {"model": "qwen2.5-coder:1.5b", "done": False, "response": "READY"},
        {"model": "qwen2.5-coder:1.5b", "done": True, "response": ""},
    ):
        def opener(request, timeout):
            return Response(json.dumps(item).encode())
        with pytest.raises(RuntimeError):
            probe.probe("qwen2.5-coder:1.5b", opener=opener,
                        clock=lambda: 1.0)


def test_probe_rejects_overlong_or_timeout_responses():
    with pytest.raises(TimeoutError):
        probe.probe("qwen2.5-coder:1.5b",
                    opener=lambda *_args, **_kwargs: Response(b"x" * 16385),
                    clock=iter([0.0, 1.0]).__next__)
    with pytest.raises(TimeoutError):
        probe.probe("qwen2.5-coder:1.5b",
                    opener=lambda *_args, **_kwargs: Response(
                        b'{"model":"qwen2.5-coder:1.5b","done":true,"response":"READY"}'
                    ),
                    clock=iter([0.0, 61.0]).__next__)


def test_dry_run_does_not_contact_or_claim_live_model(capsys):
    assert probe.main(["--model", "qwen2.5-coder:1.5b"]) == 0
    captured = json.loads(capsys.readouterr().out)
    assert captured["verified_live_inference"] is False
    assert captured["status"] == "dry_run_only"
