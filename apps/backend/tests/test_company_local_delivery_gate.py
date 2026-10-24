"""One-command local delivery stays opt-in and never impersonates human QA."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from ago.company_engineering import reviewed_candidate


@pytest.fixture
def module(monkeypatch):
    scripts = Path(__file__).resolve().parents[3] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    return importlib.import_module("ago_local_delivery_gate")


def sample(tmp_path, *, board_cleared=True):
    candidate = reviewed_candidate(json.dumps({
        "files": [
            {"path": "src/arithmetic.py", "content": "def twice(x):\n    return x * 2\n"},
            {"path": "tests/test_arithmetic.py", "content":
             "import unittest\nfrom src.arithmetic import twice\n"
             "class MathTests(unittest.TestCase):\n"
             "    def test_twice(self):\n        self.assertEqual(twice(4), 8)\n"},
        ],
        "acceptance_checks": ["Correct arithmetic with independently reviewed tests"],
    }))
    input_path = tmp_path / "board-receipt.json"
    input_path.write_text(json.dumps({
        "result": {"board_review_cleared": board_cleared,
                   "engineering_candidate": candidate}
    }), encoding="utf-8")
    return input_path, candidate


def stub_docker(monkeypatch, module, *, exit_code=0):
    from ago_verify_candidate import verify as inspect_and_run

    calls = []
    def mock_verify(staged, *, apply, confirm):
        def docker_runner(command, **options):
            calls.append((command, options))
            assert "--network" in command and "none" in command
            return SimpleNamespace(
                returncode=exit_code, stdout="AGO_UNITTEST_CASES=1\n", stderr=""
            )
        return inspect_and_run(staged, apply=apply, confirm=confirm, runner=docker_runner)
    monkeypatch.setattr(module, "verify", mock_verify)
    return calls


def test_preview_never_stages_or_runs(tmp_path, module, monkeypatch):
    input_path, candidate = sample(tmp_path)
    calls = stub_docker(monkeypatch, module)
    staged, packet = tmp_path / "staged", tmp_path / "review.json"
    preview = module.prepare(input_path, staged, packet)
    assert preview["mode"] == "inspection_only"
    assert preview["candidate_sha256"] == candidate["candidate_sha256"]
    assert preview["release_ready"] is False
    assert not staged.exists() and not packet.exists()
    assert calls == []
    with pytest.raises(PermissionError, match="explicitly confirm"):
        module.prepare(input_path, staged, packet, apply=True)
    assert not staged.exists() and not packet.exists()


def test_one_operator_confirmation_stages_tests_and_creates_pending_qa_only(
        tmp_path, module, monkeypatch):
    input_path, candidate = sample(tmp_path)
    calls = stub_docker(monkeypatch, module)
    staged, out = tmp_path / "staged", tmp_path / "qa-review.json"
    result = module.prepare(
        input_path, staged, out, apply=True, confirm=module.APPLY_CONFIRM
    )
    assert result["mode"] == "pending_independent_human_qa"
    assert result["local_unit_tests_passed"] is True
    assert result["test_case_count"] == 1
    assert result["independent_qa_approved"] is False
    assert result["github_committed"] is False
    assert result["release_ready"] is False
    assert len(calls) == 1
    handoff = json.loads(out.read_text(encoding="utf-8"))
    assert handoff["candidate_sha256"] == candidate["candidate_sha256"]
    assert handoff["qa_approved"] is False
    assert handoff["github_write_authorized"] is False
    assert handoff["release_ready"] is False
    with pytest.raises(FileExistsError):
        module.prepare(input_path, staged, out, apply=True,
                       confirm=module.APPLY_CONFIRM)
    assert len(calls) == 1


def test_failed_code_cannot_create_qa_handoff(tmp_path, module, monkeypatch):
    input_path, _ = sample(tmp_path)
    stub_docker(monkeypatch, module, exit_code=1)
    staged, out = tmp_path / "staged", tmp_path / "qa-review.json"
    result = module.prepare(input_path, staged, out,
                            apply=True, confirm=module.APPLY_CONFIRM)
    assert result["local_unit_tests_passed"] is False
    assert result["mode"] == "local_container_test_completed"
    assert result["release_ready"] is False
    assert not out.exists()
    receipt = json.loads((staged / "AGO_TEST_RECEIPT.json").read_text())
    assert receipt["tests_passed"] is False


def test_no_board_approval_no_stage_and_no_github_write(tmp_path, module, monkeypatch):
    inp, _ = sample(tmp_path, board_cleared=False)
    calls = stub_docker(monkeypatch, module)
    out, staged = tmp_path / "qa.json", tmp_path / "staged"
    with pytest.raises(PermissionError, match="complete approving AI Board"):
        module.prepare(inp, staged, out, apply=True, confirm=module.APPLY_CONFIRM)
    assert calls == [] and not staged.exists()
    assert not out.exists()


def test_packet_must_be_outside_staged_directory(tmp_path, module, monkeypatch):
    inp, _ = sample(tmp_path)
    calls = stub_docker(monkeypatch, module)
    staged = tmp_path / "candidate"
    with pytest.raises(PermissionError, match="outside staged"):
        module.prepare(
            inp, staged, staged / "qa.json", apply=True,
            confirm=module.APPLY_CONFIRM,
        )
    assert not staged.exists() and calls == []


def test_optional_github_draft_is_immutable_and_unsubmitted(
        tmp_path, module, monkeypatch):
    inp, candidate = sample(tmp_path)
    calls = stub_docker(monkeypatch, module)
    stage, out = tmp_path / "stage", tmp_path / "qa.json"
    operation_id = str(uuid4())
    options = (str(uuid4()), operation_id, "a" * 40, "Exact code pending external QA")
    summary = module.prepare(
        inp, stage, out, apply=True, confirm=module.APPLY_CONFIRM,
        github_options=options,
    )
    drafted = json.loads((stage / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").read_text())
    assert drafted["payload"]["files"] == candidate["files"]
    assert drafted["operation"] == "commit_files"
    assert json.loads(out.read_text())["proposed_github_operation_id"] == operation_id
    assert summary["github_committed"] is False
    assert summary["release_ready"] is False
    assert len(calls) == 1
