"""Founder-local saved Ollama run -> Docker QA bridge, with no auto-release."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_company_run_candidate_export import opener_for, stored_run

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def workflow(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("ago_live_to_qa")


def paths(tmp_path):
    return (tmp_path / "run.json", tmp_path / "code", tmp_path / "qa.json")


def fake_docker(monkeypatch, *, exit_code=0):
    gateway = importlib.import_module("ago_local_delivery_gate")
    from ago_verify_candidate import verify as real_verify
    calls = []

    def isolated(staged, *, apply, confirm):
        def execute(command, **kwargs):
            calls.append((command, kwargs))
            assert "--network" in command and "none" in command
            assert "--read-only" in command
            return SimpleNamespace(
                returncode=exit_code, stdout="AGO_UNITTEST_CASES=1\n", stderr=""
            )
        return real_verify(
            staged, apply=apply, confirm=confirm, runner=execute
        )
    monkeypatch.setattr(gateway, "verify", isolated)
    return calls


def test_preview_validates_authentic_board_record_without_writes(
    workflow, tmp_path
):
    source = stored_run()
    opener, requests = opener_for(source)
    export, stage, qa = paths(tmp_path)
    result = workflow.bridge(
        source["id"], export, stage, qa,
        base="http://127.0.0.1:8000", token="session", opener=opener,
    )
    assert result["mode"] == "read_only_preview"
    assert result["run_id"] == source["id"]
    assert result["candidate_sha256"]
    assert result["docker_tests_executed"] is False
    assert result["github_committed"] is False
    assert not export.exists() and not stage.exists() and not qa.exists()
    assert [r[1] for r in requests] == ["GET", "GET"]


def test_two_explicit_consents_run_one_isolated_test_and_stop_at_human_qa(
    workflow, tmp_path, monkeypatch
):
    source = stored_run()
    opener, requests = opener_for(source)
    calls = fake_docker(monkeypatch)
    export, stage, qa = paths(tmp_path)
    summary = workflow.bridge(
        source["id"], export, stage, qa,
        base="http://localhost:8000", token="session",
        apply=True, confirm_export=workflow.EXPORT_CONFIRM,
        confirm_docker=workflow.DOCKER_CONFIRM, opener=opener,
    )
    assert summary["mode"] == "pending_independent_human_qa"
    assert summary["docker_tests_executed"] is True
    assert summary["docker_tests_passed"] is True
    assert summary["qa_packet_prepared"] is True
    assert summary["docker_unittest_cases"] == 1
    assert summary["independent_human_qa_approved"] is False
    assert summary["github_operation_submitted"] is False
    assert summary["github_committed"] is False
    assert summary["release_ready"] is False
    assert len(calls) == 1
    assert [r[1] for r in requests] == ["GET"] * 4
    assert json.loads(qa.read_text())["qa_approved"] is False
    assert json.loads(export.read_text())["source"] == "ago_authenticated_founder_run"
    assert "PRIVATE FOUNDER TEXT" not in export.read_text()
    with pytest.raises(FileExistsError):
        workflow.bridge(
            source["id"], export, stage, qa,
            base="http://127.0.0.1:8000", token="session",
            apply=True, confirm_export=workflow.EXPORT_CONFIRM,
            confirm_docker=workflow.DOCKER_CONFIRM, opener=opener,
        )
    assert len(calls) == 1


def test_missing_either_confirmation_blocks_before_reads_or_docker(
    workflow, tmp_path, monkeypatch
):
    source = stored_run()
    opener, requests = opener_for(source)
    calls = fake_docker(monkeypatch)
    export, stage, qa = paths(tmp_path)
    for export_confirm, docker_confirm in (
        ("", workflow.DOCKER_CONFIRM),
        (workflow.EXPORT_CONFIRM, ""),
    ):
        with pytest.raises(PermissionError, match="Separate"):
            workflow.bridge(
                source["id"], export, stage, qa,
                base="http://127.0.0.1:8000", token="session",
                apply=True, confirm_export=export_confirm,
                confirm_docker=docker_confirm, opener=opener,
            )
    assert requests == [] and calls == []
    assert not export.exists() and not stage.exists() and not qa.exists()


def test_failed_model_receipt_or_non_founder_does_not_stage(
    workflow, tmp_path, monkeypatch
):
    source = stored_run()
    source["result"]["engineering_authorization"] = "not_requested"
    opener, _ = opener_for(source)
    calls = fake_docker(monkeypatch)
    export, stage, qa = paths(tmp_path)
    with pytest.raises(PermissionError, match="Board and real engineering"):
        workflow.bridge(
            source["id"], export, stage, qa,
            base="http://127.0.0.1:8000", token="session", opener=opener,
        )
    source["result"]["engineering_authorization"] = "implementation_stage_verified"
    outsider, _ = opener_for(source, founder=False)
    with pytest.raises(PermissionError, match="Founder role"):
        workflow.bridge(
            source["id"], export, stage, qa,
            base="http://127.0.0.1:8000", token="session", opener=outsider,
        )
    assert calls == [] and not export.exists()


def test_failed_docker_never_generates_qa_or_github_operation(
    workflow, tmp_path, monkeypatch
):
    source = stored_run()
    opener, _ = opener_for(source)
    calls = fake_docker(monkeypatch, exit_code=1)
    export, stage, qa = paths(tmp_path)
    summary = workflow.bridge(
        source["id"], export, stage, qa,
        base="http://127.0.0.1:8000", token="session",
        apply=True, confirm_export=workflow.EXPORT_CONFIRM,
        confirm_docker=workflow.DOCKER_CONFIRM, opener=opener,
    )
    assert summary["docker_tests_passed"] is False
    assert summary["qa_packet_prepared"] is False
    assert summary["github_committed"] is False
    assert export.is_file() and stage.is_dir() and not qa.exists()
    assert len(calls) == 1


def test_private_artifacts_cannot_enter_git_checkout_or_overlap(
    workflow, tmp_path
):
    export, stage, qa = paths(tmp_path)
    with pytest.raises(PermissionError, match="outside AGO checkout"):
        workflow._private_paths(ROOT / "unsafe-run.json", stage, qa)
    with pytest.raises(PermissionError, match="Distinct"):
        workflow._private_paths(export, stage, export)
    with pytest.raises(PermissionError, match="outside untrusted stage"):
        workflow._private_paths(export, stage, stage / "qa.json")
    with pytest.raises(PermissionError, match="outside untrusted stage"):
        workflow._private_paths(stage / "private.json", stage, qa)


def test_never_dispatches_non_loopback_requests(workflow, tmp_path):
    source = stored_run()
    opener, requests = opener_for(source)
    export, stage, qa = paths(tmp_path)
    with pytest.raises(ValueError, match="localhost"):
        workflow.bridge(
            source["id"], export, stage, qa,
            base="https://github.com", token="session", opener=opener,
        )
    assert not requests and not export.exists()
