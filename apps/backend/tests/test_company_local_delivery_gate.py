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


def repaired_request(tmp_path, module):
    """Model an existing failed Docker test and an unapproved source-only patch."""
    from ago.company_engineering import stage_candidate

    _, original = sample(tmp_path)
    previous = tmp_path / "failed-stage"
    stage_candidate(original, previous)
    (previous / "AGO_TEST_RECEIPT.json").write_text(json.dumps({
        "kind": "ago_local_container_unittest_receipt",
        "candidate_sha256": original["candidate_sha256"],
        "tests_executed": True, "tests_passed": False,
        "unittest_cases": 1, "docker_exit_code": 1,
        "network_disabled": True, "read_only_container": True,
        "independent_qa_approved": False, "git_committed": False,
        "release_ready": False,
    }), encoding="utf-8")
    changed = [dict(f) for f in original["files"]]
    changed[0]["content"] = "def twice(x):\n    return x * 2 + 0\n"
    updated = reviewed_candidate(json.dumps({
        "files": changed, "acceptance_checks": original["acceptance_checks"],
    }))
    repair = {
        "kind": "ago_unapproved_local_repair_proposal",
        "original_candidate_sha256": original["candidate_sha256"],
        "engineering_candidate": updated,
        "source_tests_preserved": True, "requires_new_local_docker_test": True,
        "requires_independent_human_qa": True, "qa_approved": False,
        "github_write_authorized": False, "release_ready": False,
        "automated_retry_executed": False,
    }
    inp = tmp_path / "repair-proposal.json"
    inp.write_text(json.dumps(repair), encoding="utf-8")
    return inp, previous, repair, updated


def test_repair_retest_requires_original_failed_evidence_and_keeps_qa_pending(
        tmp_path, module, monkeypatch):
    inp, previous, _, candidate = repaired_request(tmp_path, module)
    calls = stub_docker(monkeypatch, module)
    destination, packet = tmp_path / "retested", tmp_path / "retested-qa.json"
    with pytest.raises(PermissionError, match="original --repair-from"):
        module.prepare(inp, destination, packet)
    assert not destination.exists()
    preview = module.prepare(inp, destination, packet, repair_from=previous)
    assert preview["input_kind"] == "repair_pending_retest"
    assert preview["board_review_verified_from_local_receipt"] is False
    assert preview["repair_source_lineage_checked"] is True
    assert calls == []
    accepted = module.prepare(inp, destination, packet, repair_from=previous,
                              apply=True, confirm=module.APPLY_CONFIRM)
    assert accepted["mode"] == "pending_independent_human_qa"
    assert accepted["candidate_sha256"] == candidate["candidate_sha256"]
    assert accepted["independent_qa_approved"] is False
    assert accepted["github_committed"] is False
    assert len(calls) == 1
    assert json.loads(packet.read_text())["qa_approved"] is False


@pytest.mark.parametrize("tampering", [
    "missing_original", "original_digest", "modified_test", "modified_checks",
    "release_claim", "execution_claim", "original_is_not_failed", "no_source_change",
])
def test_repair_input_cannot_skip_failed_origin_or_launder_approval(
        tmp_path, module, monkeypatch, tampering):
    from ago.company_engineering import reviewed_candidate
    inp, previous, request, candidate = repaired_request(tmp_path, module)
    calls = stub_docker(monkeypatch, module)
    if tampering == "missing_original":
        previous = tmp_path / "nonexistent"
    elif tampering == "original_digest":
        request["original_candidate_sha256"] = "f" * 64
    elif tampering in ("modified_test", "modified_checks", "no_source_change"):
        changed = [dict(f) for f in candidate["files"]]
        checks = candidate["acceptance_checks"]
        if tampering == "modified_test":
            changed[1]["content"] += "# injected relaxation\n"
        elif tampering == "modified_checks":
            checks = ["Anything passes"]
        else:
            original = module.original_failed_candidate(previous)
            changed = original["files"]
        request["engineering_candidate"] = reviewed_candidate(json.dumps({
            "files": changed, "acceptance_checks": checks,
        }))
    elif tampering == "release_claim":
        request["qa_approved"] = True
    elif tampering == "execution_claim":
        request["automated_retry_executed"] = True
    else:
        receipt = previous / "AGO_TEST_RECEIPT.json"
        row = json.loads(receipt.read_text())
        row["tests_passed"] = True
        receipt.write_text(json.dumps(row))
    inp.write_text(json.dumps(request), encoding="utf-8")
    with pytest.raises((ValueError, PermissionError)):
        module.prepare(inp, tmp_path / "test", tmp_path / "qa.json",
                       repair_from=previous, apply=True, confirm=module.APPLY_CONFIRM)
    assert calls == [] and not (tmp_path / "test").exists()


def test_normal_board_record_cannot_claim_repair_lineage(tmp_path, module):
    inp, _ = sample(tmp_path)
    summary = module.prepare(inp, tmp_path / "staging", tmp_path / "qa.json")
    assert summary["board_review_verified_from_local_receipt"] is True
    assert summary["repair_source_lineage_checked"] is False
    with pytest.raises(PermissionError, match="Only an unapproved repair"):
        module.prepare(inp, tmp_path / "staging", tmp_path / "qa.json",
                       repair_from=tmp_path / "untrusted")
