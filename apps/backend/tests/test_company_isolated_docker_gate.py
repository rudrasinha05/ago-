"""Offline mocked checks for AGO's explicit Docker candidate-test boundary.

Mocks never execute model-generated source or require Docker on CI.
"""
from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path
from types import SimpleNamespace

import pytest

from ago.company_engineering import reviewed_candidate, stage_candidate

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ago_verify_candidate.py"
MODULE = run_path(str(SCRIPT))


def staged(tmp_path):
    source = {
        "files": [
            {"path": "src/mathlib.py", "content": "def add(a, b):\n    return a + b\n"},
            {"path": "tests/test_mathlib.py", "content":
             "import unittest\nfrom src.mathlib import add\n"
             "class AddTests(unittest.TestCase):\n"
             "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n"},
        ],
        "acceptance_checks": ["Check arithmetic in an isolated, reviewed test"],
    }
    directory = tmp_path / "staged"
    candidate = reviewed_candidate(json.dumps(source))
    stage_candidate(candidate, directory)
    return directory, candidate


def test_preview_is_read_only_and_requires_confirmation(tmp_path):
    directory, candidate = staged(tmp_path)
    preview = MODULE["verify"](directory)
    assert preview["status"] == "inspection_only"
    assert preview["candidate_sha256"] == candidate["candidate_sha256"]
    assert preview["tests_executed"] is False
    assert not (directory / "AGO_TEST_RECEIPT.json").exists()
    with pytest.raises(PermissionError):
        MODULE["verify"](directory, apply=True)
    with pytest.raises(ValueError):
        MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"], timeout=301)


def test_docker_command_is_offline_unprivileged_and_read_only(tmp_path):
    directory, _ = staged(tmp_path)
    command = MODULE["docker_command"](directory, "ago-qa-" + "a" * 32)
    for item in ("--network", "none", "--read-only", "--cap-drop=ALL",
                 "--security-opt=no-new-privileges", "--pull=never",
                 "--user=65534:65534", "--pids-limit=64"):
        assert item in command
    assert "dst=/work,readonly" in " ".join(command)
    assert MODULE["IMAGE"] in command
    with pytest.raises(ValueError):
        MODULE["docker_command"](directory, "untrusted-name")


def test_successful_test_evidence_does_not_imply_qa_or_release(tmp_path):
    directory, candidate = staged(tmp_path)
    commands = []
    def execute(command, **opts):
        commands.append(command)
        assert opts["timeout"] == 90
        return SimpleNamespace(returncode=0, stdout="AGO_UNITTEST_CASES=1\n",
                               stderr="test_add ... ok\n")
    record = MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"],
                              runner=execute)
    assert len(commands) == 1
    assert record["candidate_sha256"] == candidate["candidate_sha256"]
    assert record["unittest_cases"] == 1
    assert record["tests_passed"] is True
    assert record["git_committed"] is False
    assert record["independent_qa_approved"] is False
    assert record["release_ready"] is False
    assert json.loads((directory / "AGO_TEST_RECEIPT.json").read_text()) == record
    with pytest.raises(FileExistsError):
        MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"], runner=execute)
    assert len(commands) == 1


@pytest.mark.parametrize("code,cases,passed", [
    (1, "AGO_UNITTEST_CASES=2\n", False),
    (0, "Unverified Docker output\n", False),
    (0, "AGO_UNITTEST_CASES=0\n", False),
])
def test_failure_or_zero_tests_never_marks_candidate_passed(tmp_path, code, cases, passed):
    directory, _ = staged(tmp_path)
    def execute(_command, **kwargs):
        return SimpleNamespace(returncode=code, stdout=cases, stderr="")
    output = MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"],
                              runner=execute)
    assert output["tests_passed"] is passed
    assert output["release_ready"] is False


def test_tampering_unreviewed_content_and_links_are_denied(tmp_path):
    directory, _ = staged(tmp_path)
    (directory / "src" / "mathlib.py").write_text("def add(a,b): return 9\n")
    with pytest.raises(PermissionError):
        MODULE["verify"](directory)
    directory, _ = staged(tmp_path / "fresh")
    (directory / "src" / "extra.py").write_text("print('unknown')\n")
    with pytest.raises(PermissionError):
        MODULE["verify"](directory)
    directory, _ = staged(tmp_path / "linked")
    (directory / "src" / "mathlib.py").unlink()
    (directory / "src" / "mathlib.py").symlink_to(directory / "tests" / "test_mathlib.py")
    with pytest.raises(PermissionError):
        MODULE["verify"](directory)


def test_reviewed_unsubmitted_github_draft_is_allowed_only_if_exact(tmp_path):
    from uuid import uuid4
    from ago.company_engineering import draft_github_commit_operation

    directory, candidate = staged(tmp_path)
    operation = draft_github_commit_operation(
        candidate, project_id=str(uuid4()), operation_id=str(uuid4()),
        expected_sha="a" * 40, message="Founder reviewed exact staged Python source"
    )
    draft_file = directory / "AGO_UNSUBMITTED_GITHUB_OPERATION.json"
    draft_file.write_text(json.dumps(operation), encoding="utf-8")
    inspection = MODULE["verify"](directory)
    assert inspection["status"] == "inspection_only"
    assert inspection["tests_executed"] is False
    operation["payload"]["files"][0]["content"] = "def add(a,b): return 0\\n"
    draft_file.write_text(json.dumps(operation), encoding="utf-8")
    with pytest.raises(PermissionError, match="differs"):
        MODULE["verify"](directory)



def test_docker_qa_receipt_never_persists_private_stdout_or_terminal_control_codes(tmp_path):
    """Untrusted candidate test logs can contain real credentials or founder briefs."""
    import hashlib

    directory, candidate = staged(tmp_path)
    secret = "ghp_" + "a" * 32
    founder_brief = "SECRET_FOUNDER_COMPANY_BRIEF"
    combined_stdout = "AGO_UNITTEST_CASES=1\n" + founder_brief + "\n"
    combined_stderr = "\x1b[31m" + secret + "\x1b[0m\n"
    def execute(_command, **kwargs):
        return SimpleNamespace(returncode=0, stdout=combined_stdout,
                               stderr=combined_stderr)
    result = MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"],
                              runner=execute)
    saved = (directory / "AGO_TEST_RECEIPT.json").read_text(encoding="utf-8")
    assert result["candidate_sha256"] == candidate["candidate_sha256"]
    assert result["tests_passed"] is True
    assert result["output_sha256"] == hashlib.sha256(
        (combined_stdout + "\n" + combined_stderr).encode("utf-8")
    ).hexdigest()
    for disallowed in (founder_brief, secret, "\x1b[31m"):
        assert disallowed not in saved
    assert result["output_excerpt"].startswith("REDACTED:")
    assert result["independent_qa_approved"] is False



def test_failure_category_only_exposes_bounded_reason_not_raw_private_trace(tmp_path):
    directory, _ = staged(tmp_path)
    private = "FOUNDERS_CONFIDENTIAL_TEST_DATA"
    def execute(_command, **kwargs):
        return SimpleNamespace(
            returncode=1, stdout="AGO_UNITTEST_CASES=1\n",
            stderr="AssertionError: " + private + "\n",
        )
    result = MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"],
                              runner=execute)
    assert result["tests_passed"] is False
    assert result["failure_category"] == "assertion_failure"
    assert result["failure_category_advisory_only"] is True
    assert private not in (directory / "AGO_TEST_RECEIPT.json").read_text()


def test_docker_attempt_is_durable_before_runner_and_blocks_crash_replay(tmp_path):
    directory, candidate = staged(tmp_path)
    attempt_path = directory / "AGO_TEST_ATTEMPT.json"
    assert not attempt_path.exists()
    calls = []
    def crashed(command, **kwargs):
        calls.append(command)
        attempt = json.loads(attempt_path.read_text(encoding="utf-8"))
        assert attempt["candidate_sha256"] == candidate["candidate_sha256"]
        assert attempt["state"] == "outcome_unknown_until_final_receipt"
        assert attempt["tests_passed"] is False
        assert attempt["container"] in command
        raise RuntimeError("Simulated process failure after Docker started")
    with pytest.raises(RuntimeError, match="Simulated process failure"):
        MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"], runner=crashed)
    assert len(calls) == 1
    preview = MODULE["verify"](directory)
    assert preview["unresolved_execution_attempt"] is True
    with pytest.raises(FileExistsError, match="previous Docker attempt"):
        MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"], runner=crashed)
    assert len(calls) == 1


def test_passing_docker_candidate_preserves_attempt_and_final_receipt(tmp_path):
    directory, candidate = staged(tmp_path)
    def passed(_command, **_kwargs):
        assert (directory / "AGO_TEST_ATTEMPT.json").is_file()
        return SimpleNamespace(returncode=0, stdout="AGO_UNITTEST_CASES=1\n", stderr="")
    receipt = MODULE["verify"](directory, apply=True, confirm=MODULE["CONFIRM"], runner=passed)
    assert receipt["tests_passed"] is True
    assert receipt["candidate_sha256"] == candidate["candidate_sha256"]
    assert (directory / "AGO_TEST_ATTEMPT.json").is_file()
    assert (directory / "AGO_TEST_RECEIPT.json").is_file()
    assert MODULE["verify"](directory)["unresolved_execution_attempt"] is False
