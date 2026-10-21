"""No model installation, shell commands, external network or GitHub credential."""
from __future__ import annotations

import json

import pytest

from ago.company_engineering import reviewed_candidate
from ago.company_ollama_chain import run_four_role_chain


def candidate():
    return {
        "files": [
            {"path": "src/adder.py", "content": "def add(a, b):\n    return a + b\n"},
            {"path": "tests/test_adder.py",
             "content": "from src.adder import add\n\ndef test_add():\n    assert add(2, 3) == 5\n"},
        ],
        "acceptance_checks": [
            "Run isolated Python unit test with explicit operator review",
            "Inspect generated code and artifacts before a reviewed draft PR",
        ],
    }


def test_exact_reviewable_code_and_tests_parse_without_running():
    result = reviewed_candidate(json.dumps(candidate()))
    assert result["kind"] == "ago_unexecuted_engineering_candidate"
    assert [x["path"] for x in result["files"]] == [
        "src/adder.py", "tests/test_adder.py"
    ]
    assert len(result["candidate_sha256"]) == 64
    assert all(x["python_syntax_checked"] for x in result["file_evidence"])
    assert all(len(x["sha256"]) == 64 for x in result["file_evidence"])
    assert result["source_parse_passed"] is True
    assert result["tests_executed"] is False
    assert result["github_committed"] is False
    assert result["publishable"] is False
    reversed_keys = dict(reversed(list(candidate().items())))
    assert reviewed_candidate(json.dumps(reversed_keys))["candidate_sha256"] == result[
        "candidate_sha256"
    ]


@pytest.mark.parametrize("change", [
    lambda x: x.update({"files": [{"path": "src/foo.py", "content": "pass\n"}]}),
    lambda x: x["files"][0].update({"path": "../src/bad.py"}),
    lambda x: x["files"][0].update({"path": ".github/workflows/hijack.yml"}),
    lambda x: x["files"][0].update({"path": "src/.env"}),
    lambda x: x["files"][0].update({"path": "src/evil.exe"}),
    lambda x: x["files"][0].update({"content": "def broken(\n"}),
    lambda x: x["files"][0].update({"content": "-----BEGIN PRIVATE KEY-----"}),
    lambda x: x["files"][1].update({"path": "src/not_a_test.py"}),
    lambda x: x["acceptance_checks"].clear(),
    lambda x: x.update({"extra": "unreviewed field"}),
    lambda x: x["files"].append(x["files"][0]),
])
def test_incorrect_or_dangerous_candidates_are_rejected(change):
    document = candidate()
    change(document)
    with pytest.raises(ValueError):
        reviewed_candidate(json.dumps(document))


def test_no_markdown_fences_and_no_overlong_model_output():
    with pytest.raises(ValueError):
        reviewed_candidate(chr(96) * 3 + "json\n" + json.dumps(candidate()))
    with pytest.raises(ValueError):
        reviewed_candidate("x" * 12001)
    with pytest.raises(ValueError):
        reviewed_candidate("[]")


def participants():
    roles = ["ceo", "cto", "finance", "risk", "quality", "pm", "employee"]
    return [
        {"role": role, "employee_id": str(i + 100), "employee_name": role.upper()}
        for i, role in enumerate(roles)
    ]


def fake_task():
    from types import SimpleNamespace
    return SimpleNamespace(
        id="test-project-task",
        project_context={
            "title": "Implement small Python arithmetic library",
            "brief": "One deterministic addition function with a unit test",
            "intake_id": "founder-project",
        },
    )


def test_full_board_then_employee_produces_persistable_review_package():
    class SevenRoleModel:
        def __init__(self):
            self.calls = []

        def generate(self, prompt):
            self.calls.append(prompt)
            if "ROLE: EMPLOYEE\n" in prompt:
                return json.dumps(candidate())
            return "BOARD_RECOMMENDATION: APPROVE\nDECISION: scoped work"

    model = SevenRoleModel()
    result = run_four_role_chain(
        task=fake_task(), participants=participants(),
        provider=model, engineering_candidates=True,
    )
    assert len(model.calls) == 7
    assert "Produce ONLY one valid JSON object" in model.calls[-1]
    assert result["engineering_candidate_status"] == "syntax_reviewed"
    assert len(result["engineering_candidate"]["files"]) == 2
    assert result["engineering_candidate"]["tests_executed"] is False
    assert result["board_review_cleared"] is True
    assert result["handoff_complete"] is True
    assert result["github_commits_created"] is False
    assert result["project_released"] is False
    assert result["requires_human_qa"] is True


def test_board_deny_never_invokes_source_generation():
    class RiskDeny:
        def __init__(self):
            self.calls = []

        def generate(self, prompt):
            self.calls.append(prompt)
            if "ROLE: RISK\n" in prompt:
                return "BOARD_RECOMMENDATION: DENY\nRISKS: check scope"
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: review"

    model = RiskDeny()
    result = run_four_role_chain(
        task=fake_task(), participants=participants(),
        provider=model, engineering_candidates=True,
    )
    assert len(model.calls) == 4
    assert result["board_blocked"] is True
    assert result["engineering_candidate"] is None
    assert result["engineering_candidate_status"] == "not_requested"


def test_invalid_model_source_fails_closed_without_hidden_code_execution():
    class InvalidSource:
        def generate(self, prompt):
            if "ROLE: EMPLOYEE\n" in prompt:
                return "{not valid json"
            return "BOARD_RECOMMENDATION: APPROVE\nDECISION: scoped review"

    with pytest.raises(ValueError, match="JSON document"):
        run_four_role_chain(
            task=fake_task(), participants=participants(),
            provider=InvalidSource(), engineering_candidates=True,
        )


def test_two_seat_drafting_cannot_spoof_full_board_engineering():
    small = [participants()[0], participants()[1], participants()[5], participants()[6]]
    with pytest.raises(PermissionError):
        run_four_role_chain(
            task=fake_task(), participants=small,
            provider=None, engineering_candidates=True,
        )
