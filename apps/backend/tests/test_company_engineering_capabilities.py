"""Engine capability is a server configuration fact, never fictional live work."""
from __future__ import annotations

import pytest

from ago.api_agents import local_engineering_status


@pytest.fixture
def opt_in(monkeypatch):
    for key, value in {
        "AGO_ENVIRONMENT": "development",
        "AGO_LLM_PROVIDER": "ollama_local",
        "AGO_ENABLE_LOCAL_MODELS": "true",
        "AGO_LOCAL_COMPANY_CHAIN": "true",
        "AGO_LOCAL_FULL_BOARD_REVIEW": "true",
        "AGO_LOCAL_ENGINEERING_CANDIDATES": "true",
        "AGO_LLM_MODEL": "qwen2.5-coder:1.5b",
        "AGO_ENABLE_PAID_MODELS": "false",
    }.items():
        monkeypatch.setenv(key, value)


def test_local_engineering_config_requires_every_explicit_flag(opt_in, monkeypatch):
    report = local_engineering_status()
    assert report["kind"] == "ago_local_engineering_capabilities"
    assert report["engineering_enabled"] is True
    assert report["required_roles"] == 7
    assert report["provider_mode"] == "ollama_local"
    assert report["model_tag"] == "qwen2.5-coder:1.5b"
    assert report["model_inference_verified"] is False
    assert report["board_or_task_approval_verified"] is False
    assert report["github_write_authorized"] is False
    assert report["release_ready"] is False
    for key in (
        "AGO_ENABLE_LOCAL_MODELS", "AGO_LOCAL_COMPANY_CHAIN",
        "AGO_LOCAL_FULL_BOARD_REVIEW", "AGO_LOCAL_ENGINEERING_CANDIDATES",
    ):
        monkeypatch.setenv(key, "false")
        disabled = local_engineering_status()
        assert disabled["engineering_enabled"] is False
        assert disabled["provider_mode"] == "disabled"
        monkeypatch.setenv(key, "true")


@pytest.mark.parametrize(("name", "value"), [
    ("AGO_ENVIRONMENT", "production"),
    ("AGO_LLM_PROVIDER", "paid"),
    ("AGO_LLM_MODEL", ""),
    ("AGO_ENABLE_PAID_MODELS", "true"),
])
def test_paid_production_or_missing_local_model_tag_never_claim_engineering(
    opt_in, monkeypatch, name, value
):
    monkeypatch.setenv(name, value)
    report = local_engineering_status()
    assert report["engineering_enabled"] is False
    assert report["model_tag"] is None
    assert report["model_inference_verified"] is False
    assert report["release_ready"] is False


def test_anonymous_cannot_probe_company_local_engineering_flags(monkeypatch):
    from fastapi.testclient import TestClient
    from ago.main import create_app
    with TestClient(create_app()) as client:
        assert client.get("/v1/agents/engineering-capabilities").status_code == 401
