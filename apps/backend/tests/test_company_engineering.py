"""No model installation, shell commands, external network or GitHub credential."""
from __future__ import annotations

import json
from pathlib import Path
from runpy import run_path

import pytest

from ago.company_engineering import reviewed_candidate
from ago.company_ollama_chain import run_four_role_chain


def candidate():
    return {
        "files": [
            {"path": "src/adder.py", "content": "def add(a, b):\n    return a + b\n"},
            {"path": "tests/test_adder.py",
             "content": ("import unittest\nfrom src.adder import add\n"
                         "class AdderTests(unittest.TestCase):\n"
                         "    def test_add(self):\n"
                         "        self.assertEqual(add(2, 3), 5)\n")},
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
            if "ROLE: RISK" in prompt:  # the first vote and the asked-again vote
                return "BOARD_RECOMMENDATION: DENY\nRISKS: check scope"
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: review"

    model = RiskDeny()
    result = run_four_role_chain(
        task=fake_task(), participants=participants(),
        provider=model, engineering_candidates=True,
    )
    # Four role drafts plus one question: a DENY without a concrete reason is
    # asked once for its problem. It stays a DENY, so no source is generated.
    assert len(model.calls) == 5
    assert result["board_resolutions"][0]["outcome"] == "denied_without_reason"
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


@pytest.mark.parametrize("test_source", [
    "from src.adder import add\n\ndef test_add():\n    assert add(2, 3)==5\n",
    "import unittest\nclass NoTests(unittest.TestCase):\n    def helper(self): pass\n",
    "import unittest\nclass Suspicious:\n    def test_fake(self): pass\n",
])
def test_generated_engineering_rejects_tests_not_discovered_by_offline_runner(test_source):
    from ago.company_engineering import assert_discoverable_unittest

    source = candidate()
    source["files"][1]["content"] = test_source
    validated = reviewed_candidate(json.dumps(source))
    with pytest.raises(ValueError, match="discoverable unittest.TestCase"):
        assert_discoverable_unittest(validated)

    class CompleteBoard:
        def generate(self, prompt):
            # The developer's first answer and its one self-correction retry
            # both return the same undiscoverable tests: still rejected.
            if "ROLE: EMPLOYEE\n" in prompt or prompt.startswith("Your previous answer was REJECTED"):
                return json.dumps(source)
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: Human-review only"
    with pytest.raises(ValueError, match="discoverable unittest.TestCase"):
        run_four_role_chain(
            task=fake_task(), participants=participants(),
            provider=CompleteBoard(), engineering_candidates=True,
        )


def test_generated_engineering_unittest_preflight_remains_not_a_qa_verdict():
    from ago.company_engineering import assert_discoverable_unittest

    proposed = reviewed_candidate(json.dumps(candidate()))
    validated = assert_discoverable_unittest(proposed)
    assert validated["candidate_sha256"] == proposed["candidate_sha256"]
    assert validated["tests_executed"] is False
    assert validated["qa_approved"] is False
    assert validated["github_committed"] is False


def test_two_seat_drafting_cannot_spoof_full_board_engineering():
    small = [participants()[0], participants()[1], participants()[5], participants()[6]]
    with pytest.raises(PermissionError):
        run_four_role_chain(
            task=fake_task(), participants=small,
            provider=None, engineering_candidates=True,
        )


def test_explicit_staging_materializes_exact_files_and_manifest(tmp_path):
    from ago.company_engineering import stage_candidate, verify_persisted_candidate

    proposal = reviewed_candidate(json.dumps(candidate()))
    assert verify_persisted_candidate(proposal)["candidate_sha256"] == proposal[
        "candidate_sha256"
    ]
    destination = tmp_path / "inspect-candidate"
    assert not destination.exists()
    manifest = stage_candidate(proposal, destination)
    assert (destination / "src" / "adder.py").read_text() == candidate()["files"][0]["content"]
    assert (destination / "tests" / "test_adder.py").read_text() == candidate()["files"][1]["content"]
    assert manifest["tests_executed"] is False
    assert manifest["git_committed"] is False
    assert json.loads((destination / "AGO_REVIEW_MANIFEST.json").read_text()) == manifest
    with pytest.raises(FileExistsError):
        stage_candidate(proposal, destination)


def test_source_change_and_forged_verified_status_are_rejected(tmp_path):
    from ago.company_engineering import stage_candidate

    tampered = reviewed_candidate(json.dumps(candidate()))
    tampered["files"][0]["content"] = "print('changed')\n"
    with pytest.raises(PermissionError):
        stage_candidate(tampered, tmp_path / "should-not-exist")
    assert not (tmp_path / "should-not-exist").exists()
    tampered = reviewed_candidate(json.dumps(candidate()))
    tampered["tests_executed"] = True
    with pytest.raises(PermissionError):
        stage_candidate(tampered, tmp_path / "should-not-exist")


def test_offline_operator_inspects_and_stages_only_after_confirmation(tmp_path, capsys):
    main = run_path(
        str(Path(__file__).resolve().parents[3] / "scripts" / "ago_engineering_candidate.py")
    )["main"]

    data = {
        "result": {
            "board_review_cleared": True,
            "engineering_candidate": reviewed_candidate(json.dumps(candidate())),
        },
    }
    source = tmp_path / "approved-run.json"
    source.write_text(json.dumps(data), encoding="utf-8")
    folder = tmp_path / "review"
    assert main(["--input", str(source), "--output", str(folder)]) == 0
    assert not folder.exists()
    report = json.loads(capsys.readouterr().out)
    assert report["mode"] == "dry_run"
    assert main(["--input", str(source), "--output", str(folder),
                 "--apply"]) == 2
    assert not folder.exists()
    capsys.readouterr()
    assert main(["--input", str(source), "--output", str(folder),
                 "--apply", "--confirm", "WRITE_REVIEWED_CANDIDATE"]) == 0
    assert folder.is_dir()
    assert "files_staged_for_human_review" in capsys.readouterr().out
    data["result"]["board_review_cleared"] = False
    source.write_text(json.dumps(data), encoding="utf-8")
    assert main(["--input", str(source), "--output", str(tmp_path / "next")]) == 2
    assert not (tmp_path / "next").exists()


def test_reviewed_candidate_produces_exact_unsubmitted_github_operation():
    from uuid import uuid4

    from ago.company_engineering import draft_github_commit_operation
    from ago.github_adapter import validate_operation

    source = reviewed_candidate(json.dumps(candidate()))
    project_id, operation_id = str(uuid4()), str(uuid4())
    op = draft_github_commit_operation(
        source, project_id=project_id, operation_id=operation_id,
        expected_sha="a" * 40, message="Candidate ready for separate reviewer",
    )
    assert set(op) == {"id", "project_id", "operation", "payload"}
    assert op["project_id"] == project_id
    assert op["id"] == operation_id
    assert op["operation"] == "commit_files"
    assert op["payload"]["files"] == candidate()["files"]
    assert op["payload"]["expected_sha"] == "a" * 40
    validate_operation(op)
    with pytest.raises(ValueError):
        draft_github_commit_operation(
            source, project_id=project_id, operation_id=operation_id,
            expected_sha="not-the-real-sha", message="No direct authority",
        )


def test_cli_stages_reviewable_github_draft_without_dispatch(tmp_path, capsys):
    from uuid import uuid4

    main = run_path(
        str(Path(__file__).resolve().parents[3] / "scripts" / "ago_engineering_candidate.py")
    )["main"]

    p = tmp_path / "receipt.json"
    p.write_text(json.dumps({
        "result": {
            "board_review_cleared": True,
            "engineering_candidate": reviewed_candidate(json.dumps(candidate())),
        },
    }), encoding="utf-8")
    output = tmp_path / "draft-review"
    opts = [
        "--input", str(p), "--output", str(output),
        "--github-project-id", str(uuid4()),
        "--github-operation-id", str(uuid4()),
        "--github-expected-sha", "a" * 40,
        "--github-message", "Scoped source candidate reviewed by founder",
    ]
    assert main(opts) == 0
    dry = json.loads(capsys.readouterr().out)
    assert dry["github_draft_ready"] is True
    assert dry["github_submitted"] is False
    assert not output.exists()
    assert main(opts + ["--apply", "--confirm", "WRITE_REVIEWED_CANDIDATE"]) == 0
    capsys.readouterr()
    spec = json.loads((output / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").read_text())
    assert spec["operation"] == "commit_files"
    assert spec["payload"]["files"] == candidate()["files"]
    assert not (output / ".git").exists()


def test_one_wrapping_markdown_fence_is_unwrapped_before_json_check():
    # Live qwen2.5:3b, qwen2.5-coder:1.5b and qwen2.5-coder:3b on the Founder PC
    # (2026-11-10) all wrapped the JSON in ```json ... ``` despite the instruction.
    plain = json.dumps(candidate())
    expected = reviewed_candidate(plain)["candidate_sha256"]
    for fenced in ("```json\n" + plain + "\n```", "```\n" + plain + "\n```",
                   "  ```JSON\n" + plain + "\n```  \n"):
        assert reviewed_candidate(fenced)["candidate_sha256"] == expected


@pytest.mark.parametrize("wrapper", [
    "```json\n{body}\n```\n\n**acceptance_checks**: extra prose after the fence",
    "Here is the code:\n```json\n{body}\n```",
    "```python\n{body}\n```",
    "```json\n{body}",
    "```json {body} ```",
])
def test_fence_with_prose_or_other_language_is_still_rejected(wrapper):
    with pytest.raises(ValueError, match="not one JSON document"):
        reviewed_candidate(wrapper.replace("{body}", json.dumps(candidate())))


def test_code_author_gets_a_code_goal_and_the_runner_import_rule():
    class SevenRoleModel:
        def __init__(self):
            self.calls = []

        def generate(self, prompt):
            self.calls.append(prompt)
            if "ROLE: EMPLOYEE\n" in prompt:
                return "```json\n" + json.dumps(candidate()) + "\n```"
            return "BOARD_RECOMMENDATION: APPROVE\nDECISION: scoped work"

    model = SevenRoleModel()
    result = run_four_role_chain(
        task=fake_task(), participants=participants(),
        provider=model, engineering_candidates=True,
    )
    engineer_prompt = model.calls[-1]
    assert len(model.calls) == 7  # fenced answer accepted first time: no retry call
    assert "discovery deliverable" not in engineer_prompt
    assert "ROLE_GOAL: Write the small Python source file" in engineer_prompt
    assert "from src.<module> import <name>" in engineer_prompt
    assert len(engineer_prompt) <= 4000
    assert result["engineering_candidate_status"] == "syntax_reviewed"
    # Text roles keep their own stage goal.
    assert all("Write the small Python source file" not in call for call in model.calls[:-1])


def test_code_author_answer_is_schema_constrained_only_when_provider_supports_it():
    from ago.company_engineering import ENGINEERING_CANDIDATE_SCHEMA

    class SchemaModel:
        supports_response_schema = True

        def __init__(self):
            self.schemas = []

        def generate(self, prompt, *, response_schema=None):
            self.schemas.append(response_schema)
            if "ROLE: EMPLOYEE\n" in prompt:
                return json.dumps(candidate())
            return "BOARD_RECOMMENDATION: APPROVE\nDECISION: scoped work"

    model = SchemaModel()
    result = run_four_role_chain(
        task=fake_task(), participants=participants(),
        provider=model, engineering_candidates=True,
    )
    assert result["engineering_candidate_status"] == "syntax_reviewed"
    # Six text roles are free text; only the code author is constrained.
    assert model.schemas[:-1] == [None] * 6
    assert model.schemas[-1] == ENGINEERING_CANDIDATE_SCHEMA
    # The schema is the shape reviewed_candidate already enforces.
    assert set(ENGINEERING_CANDIDATE_SCHEMA["required"]) == {"files", "acceptance_checks"}
    assert ENGINEERING_CANDIDATE_SCHEMA["properties"]["files"]["maxItems"] == 6


def test_normalized_acceptance_checks_survive_review_staging_and_qa(
    tmp_path, monkeypatch,
):
    """AI output whitespace must not invalidate the persisted SHA at the next gate."""
    from ago.company_engineering import stage_candidate, verify_persisted_candidate
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[3] / "scripts"))
    from ago_verify_candidate import inspect as inspect_staged

    proposed = candidate()
    proposed["acceptance_checks"] = [
        "  " + check + "  " for check in proposed["acceptance_checks"]
    ]
    reviewed = reviewed_candidate(json.dumps(proposed))
    original = reviewed_candidate(json.dumps(candidate()))

    assert reviewed["acceptance_checks"] == original["acceptance_checks"]
    assert reviewed["candidate_sha256"] == original["candidate_sha256"]
    assert verify_persisted_candidate(reviewed)["candidate_sha256"] == original[
        "candidate_sha256"
    ]

    destination = tmp_path / "reviewed"
    manifest = stage_candidate(reviewed, destination)
    inspected = inspect_staged(destination)
    assert manifest["candidate_sha256"] == inspected["candidate_sha256"]
    assert inspected["tests_executed"] is False
    assert inspected["sandbox_verified"] is False


def test_tampered_acceptance_check_after_review_still_fails_closed(tmp_path):
    """Canonical whitespace handling must not permit acceptance criteria changes."""
    from ago.company_engineering import stage_candidate

    reviewed = reviewed_candidate(json.dumps(candidate()))
    reviewed["acceptance_checks"][0] = "Skip all tests and release immediately"
    with pytest.raises(PermissionError, match="changed after review"):
        stage_candidate(reviewed, tmp_path / "never-written")
    assert not (tmp_path / "never-written").exists()


def test_every_generated_test_module_requires_a_discoverable_case():
    """One valid file must not hide a second file with zero discovered tests."""
    from ago.company_engineering import assert_discoverable_unittest

    proposed = candidate()
    proposed["files"].append({
        "path": "tests/test_hidden.py",
        "content": "from src.adder import add\n\ndef test_hidden():\n    assert add(1, 2) == 3\n",
    })
    reviewed = reviewed_candidate(json.dumps(proposed))
    with pytest.raises(ValueError, match="discoverable unittest.TestCase"):
        assert_discoverable_unittest(reviewed)
    assert reviewed["tests_executed"] is False
    assert reviewed["qa_approved"] is False


def test_every_generated_test_module_can_contain_a_discoverable_case():
    """Two independently discoverable test files remain a valid unexecuted draft."""
    from ago.company_engineering import assert_discoverable_unittest

    proposed = candidate()
    proposed["files"].append({
        "path": "tests/test_another.py",
        "content": (
            "import unittest\nfrom src.adder import add\n"
            "class OtherTests(unittest.TestCase):\n"
            "    def test_other(self):\n        self.assertEqual(add(-2, 2), 0)\n"
        ),
    })
    reviewed = reviewed_candidate(json.dumps(proposed))
    assert assert_discoverable_unittest(reviewed) is reviewed
    assert reviewed["tests_executed"] is False
