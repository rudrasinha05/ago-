"""Independent QA handoff is an unprivileged local request, never an approval."""
from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path
from uuid import uuid4

import pytest

from ago.company_engineering import (
    draft_github_commit_operation,
    reviewed_candidate,
    stage_candidate,
)

SCRIPTS = Path(__file__).resolve().parents[3] / "scripts"


@pytest.fixture
def module(monkeypatch):
    monkeypatch.syspath_prepend(str(SCRIPTS))
    return run_path(str(SCRIPTS / "ago_qa_review_packet.py"))


def staged(tmp_path):
    source = {
        "files": [
            {"path": "src/arithmetic.py",
             "content": "def multiply(a,b):\n    return a*b\n"},
            {"path": "tests/test_arithmetic.py",
             "content": "import unittest\nfrom src.arithmetic import multiply\n"
                        "class Arithmetic(unittest.TestCase):\n"
                        "    def test_multiply(self):\n"
                        "        self.assertEqual(multiply(3,4),12)\n"},
        ],
        "acceptance_checks": ["Test multiplication and independent QA review"],
    }
    candidate = reviewed_candidate(json.dumps(source))
    location = tmp_path / "candidate"
    stage_candidate(candidate, location)
    return location, candidate


def receipt(location, candidate, **overrides):
    details = {
        "kind": "ago_local_container_unittest_receipt",
        "candidate_sha256": candidate["candidate_sha256"],
        "tests_executed": True,
        "tests_passed": True,
        "unittest_cases": 1,
        "docker_exit_code": 0,
        "network_disabled": True,
        "read_only_container": True,
        "git_committed": False,
        "independent_qa_approved": False,
        "release_ready": False,
        "output_excerpt": "synthetic test receipt for unit tests only",
    }
    details.update(overrides)
    (location / "AGO_TEST_RECEIPT.json").write_text(json.dumps(details), encoding="utf-8")
    return details


def test_passed_evidence_creates_pending_review_not_a_QA_verdict(tmp_path, module):
    location, candidate = staged(tmp_path)
    receipt(location, candidate)
    result = module["packet"](location)
    assert result["candidate_sha256"] == candidate["candidate_sha256"]
    assert result["unittest_cases"] == 1
    assert result["files"] == ["src/arithmetic.py", "tests/test_arithmetic.py"]
    assert len(result["local_test_receipt_sha256"]) == 64
    assert result["untrusted_local_receipt"] is True
    assert result["test_evidence_only"] is True
    assert result["independent_human_qa_pending"] is True
    assert result["qa_approved"] is False
    assert result["github_write_authorized"] is False
    assert result["release_ready"] is False
    assert result["proposed_github_operation_id"] is None


@pytest.mark.parametrize("overrides", [
    {"tests_executed": False},
    {"tests_passed": False},
    {"unittest_cases": 0},
    {"unittest_cases": True},
    {"docker_exit_code": 1},
    {"network_disabled": False},
    {"read_only_container": False},
    {"git_committed": True},
    {"independent_qa_approved": True},
    {"release_ready": True},
    {"candidate_sha256": "f" * 64},
])
def test_failed_tampered_or_overclaimed_receipts_rejected(tmp_path, module, overrides):
    location, candidate = staged(tmp_path)
    receipt(location, candidate, **overrides)
    with pytest.raises(PermissionError, match="local passing smoke"):
        module["packet"](location)


def test_missing_receipt_unknown_code_and_symlink_rejected(tmp_path, module):
    location, candidate = staged(tmp_path)
    with pytest.raises(ValueError, match="receipt"):
        module["packet"](location)
    receipt(location, candidate)
    (location / "src" / "arithmetic.py").write_text("def multiply(a,b): return 0\n")
    with pytest.raises(PermissionError, match="Staged file bytes"):
        module["packet"](location)
    location2, candidate2 = staged(tmp_path / "fresh")
    receipt(location2, candidate2)
    original = location2 / "AGO_TEST_RECEIPT.json"
    elsewhere = tmp_path / "elsewhere.json"
    elsewhere.write_bytes(original.read_bytes())
    original.unlink()
    original.symlink_to(elsewhere)
    with pytest.raises(ValueError, match="regular"):
        module["packet"](location2)


def test_exact_unsubmitted_github_draft_is_linked_but_never_executed(tmp_path, module):
    location, candidate = staged(tmp_path)
    receipt(location, candidate)
    operation = draft_github_commit_operation(
        candidate, project_id=str(uuid4()), operation_id=str(uuid4()),
        expected_sha="a" * 40, message="Verified sample for separate review"
    )
    (location / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").write_text(
        json.dumps(operation), encoding="utf-8"
    )
    packet = module["packet"](location)
    assert packet["proposed_github_operation_id"] == operation["id"]
    assert packet["github_write_authorized"] is False
    operation["payload"]["files"][0]["content"] += "# unreviewed change\n"
    (location / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").write_text(
        json.dumps(operation), encoding="utf-8"
    )
    with pytest.raises(PermissionError, match="differs"):
        module["packet"](location)


def test_cli_preview_is_readonly_and_explicit_write_is_once_outside_source(
        tmp_path, module, capsys):
    location, candidate = staged(tmp_path)
    receipt(location, candidate)
    result_path = tmp_path / "handoff.json"
    args = ["--staged-directory", str(location), "--output", str(result_path)]
    assert module["main"](args) == 0
    assert not result_path.exists()
    assert module["main"]([*args, "--apply"]) == 2
    assert not result_path.exists()
    full = [*args, "--apply", "--confirm", "PREPARE_INDEPENDENT_QA_REVIEW"]
    assert module["main"](full) == 0
    saved = json.loads(result_path.read_text(encoding="utf-8"))
    assert saved["candidate_sha256"] == candidate["candidate_sha256"]
    assert saved["qa_approved"] is False
    assert module["main"](full) == 2
    internal = location / "AGO_QA_HANDOFF.json"
    assert module["main"]([
        "--staged-directory", str(location), "--output", str(internal),
        "--apply", "--confirm", "PREPARE_INDEPENDENT_QA_REVIEW",
    ]) == 2
    assert not internal.exists()
    assert "blocked" in capsys.readouterr().err
