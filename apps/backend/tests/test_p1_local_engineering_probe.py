"""No live model/network in CI: AI-005 standalone probe remains opt-in."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from ago.company_engineering import ENGINEERING_CANDIDATE_SCHEMA


@pytest.fixture
def script(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    module = importlib.import_module("ago_local_engineering_probe")
    for key, value in {
        "AGO_ENVIRONMENT": "development",
        "AGO_LLM_PROVIDER": "ollama_local",
        "AGO_ENABLE_LOCAL_MODELS": "true",
        "AGO_ENABLE_PAID_MODELS": "false",
        "AGO_LLM_MODEL": "qwen2.5-coder:3b",
    }.items():
        monkeypatch.setenv(key, value)
    return module


def candidate():
    return json.dumps({
        "files": [
            {"path": "src/arithmetic.py", "content": "def add(a,b):\n    return a+b\n"},
            {"path": "tests/test_arithmetic.py", "content": (
                "import unittest\nfrom src.arithmetic import add\n"
                "class ArithmeticTests(unittest.TestCase):\n"
                "    def test_sum(self):\n        self.assertEqual(add(2, -3), -1)\n"
            )},
        ],
        "acceptance_checks": ["  Check normal and negative sums  "],
    })


def test_preview_is_readonly_and_never_calls_model(tmp_path, script):
    calls = []
    provider = SimpleNamespace(
        supports_response_schema=True,
        generate=lambda *_args, **_kwargs: calls.append(1),
    )
    destination = tmp_path / "receipt.json"
    result = script.probe(destination, provider=provider)
    assert result["mode"] == "inspection_only"
    assert result["real_ago_founder_task_executed"] is False
    assert result["code_candidate_static_reviewed"] is False
    assert calls == [] and not destination.exists()


def test_real_schema_path_with_injected_model_is_not_claimed_live(
    tmp_path, script,
):
    calls = []
    def generate(prompt, *, response_schema=None):
        calls.append((prompt, response_schema))
        return candidate()

    provider = SimpleNamespace(supports_response_schema=True, generate=generate)
    destination = tmp_path / "receipt.json"
    result = script.probe(
        destination, apply=True, confirm=script.CONFIRM, provider=provider,
        clock=iter([1.0, 1.75]).__next__,
    )
    assert len(calls) == 1
    assert len(calls[0][0]) < 4000
    assert calls[0][1] == ENGINEERING_CANDIDATE_SCHEMA
    assert result["code_candidate_static_reviewed"] is True
    assert result["schema_requested"] is True
    assert len(result["candidate_sha256"]) == 64
    assert result["source_file_count"] == result["test_file_count"] == 1
    assert result["local_ollama_response_observed"] is False
    assert result["real_ago_founder_task_executed"] is False
    assert result["board_approval_verified"] is False
    assert result["tests_executed"] is False
    assert result["independent_human_qa_approved"] is False
    assert result["github_committed"] is False
    assert result["release_ready"] is False
    persisted = destination.read_text(encoding="utf-8")
    assert "def add" not in persisted
    assert "class ArithmeticTests" not in persisted
    assert json.loads(persisted) == result
    with pytest.raises(FileExistsError):
        script.probe(destination, apply=True, confirm=script.CONFIRM, provider=provider)
    assert len(calls) == 1


@pytest.mark.parametrize(("setting", "value"), [
    ("AGO_ENVIRONMENT", "production"),
    ("AGO_LLM_PROVIDER", "paid"),
    ("AGO_ENABLE_LOCAL_MODELS", "false"),
    ("AGO_ENABLE_PAID_MODELS", "true"),
])
def test_nonlocal_or_paid_configuration_never_calls_provider(
    tmp_path, script, monkeypatch, setting, value,
):
    calls = []
    provider = SimpleNamespace(generate=lambda _: calls.append(1))
    monkeypatch.setenv(setting, value)
    destination = tmp_path / "blocked.json"
    with pytest.raises(PermissionError):
        script.probe(destination, apply=True, confirm=script.CONFIRM, provider=provider)
    assert calls == [] and not destination.exists()


def test_missing_confirmation_or_invalid_result_cannot_write_receipt(
    tmp_path, script,
):
    calls = []
    fake = SimpleNamespace(generate=lambda _: calls.append(1) or "invalid json")
    dest = tmp_path / "unverified.json"
    with pytest.raises(PermissionError):
        script.probe(dest, apply=True, provider=fake)
    assert calls == []
    with pytest.raises(ValueError):
        script.probe(dest, apply=True, confirm=script.CONFIRM, provider=fake)
    assert calls == [1] and not dest.exists()


def test_undiscoverable_test_fails_closed_without_receipt(tmp_path, script):
    bad = json.loads(candidate())
    bad["files"][1]["content"] = (
        "from src.arithmetic import add\ndef test_add():\n    assert add(1,2)==3\n"
    )
    provider = SimpleNamespace(generate=lambda _: json.dumps(bad))
    output = tmp_path / "failed.json"
    with pytest.raises(ValueError, match="discoverable unittest.TestCase"):
        script.probe(output, apply=True, confirm=script.CONFIRM, provider=provider)
    assert not output.exists()
