"""Founder may export ONLY the exact persisted, Board-cleared real AI run."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest

from ago.company_engineering import reviewed_candidate

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "ago_pull_candidate.py"


@pytest.fixture
def exporter(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("ago_pull_candidate_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def real_candidate():
    return reviewed_candidate(json.dumps({
        "files": [
            {"path": "src/arithmetic.py", "content": "def add(a,b):\n    return a+b\n"},
            {"path": "tests/test_arithmetic.py",
             "content": ("import unittest\nfrom src.arithmetic import add\n"
                         "class TestArithmetic(unittest.TestCase):\n"
                         "    def test_add(self):\n"
                         "        self.assertEqual(add(3,4),7)\n")},
        ],
        "acceptance_checks": ["Adds two integers with a standard-library unit test"],
    }))


def stored_run():
    task_id = str(uuid4())
    employees = [str(uuid4()) for _ in range(7)]
    names = ("Strategy & Vision", "Technology Oversight", "Finance & Budget",
             "Risk & Compliance", "Quality & Release")
    roles = ("ceo", "cto", "finance", "risk", "quality", "pm", "employee")
    return {
        "id": str(uuid4()), "task_id": task_id,
        "status": "completed",
        "result": {
            "kind": "local_company_governed_handoff",
            "task_id": task_id, "project_id": str(uuid4()),
            "board_review_mode": "full_five_seat",
            "board_review_cleared": True, "board_blocked": False,
            "roles_expected": 7, "roles_completed": 7,
            "handoff_complete": True, "requires_human_qa": True,
            "github_commits_created": False, "project_released": False,
            "engineering_candidate_status": "syntax_reviewed",
            "engineering_candidate": real_candidate(),
            "board_recommendations": [
                {"seat": name, "employee_id": employees[i],
                 "recommendation": "approve", "verifiable_model_output": True,
                 "binding_authorization": False}
                for i, name in enumerate(names)
            ],
            "handoffs": [
                {"role": role, "employee_id": employees[i],
                 "draft": "PRIVATE FOUNDER TEXT MUST NEVER EXPORT"}
                for i, role in enumerate(roles)
            ],
            "private_runtime_data": "PRIVATE FOUNDER TEXT MUST NEVER EXPORT",
        },
    }


class MockReply:
    def __init__(self, data):
        self.data = json.dumps(data).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, _n=-1):
        return self.data


def opener_for(record, *, founder=True):
    requests = []
    def open_request(req, timeout):
        requests.append((req.full_url, req.get_method(), timeout,
                         req.get_header("Authorization")))
        if req.full_url.endswith("/v1/console/me"):
            return MockReply({"roles": ["founder"] if founder else ["employee"]})
        if req.full_url.endswith("/v1/agents/runs"):
            return MockReply([record])
        raise AssertionError("Unexpected endpoint")
    return open_request, requests


def test_real_persisted_run_export_is_minimal_and_stages_with_existing_pipeline(
    exporter, tmp_path, monkeypatch
):
    record = stored_run()
    io_mock, requests = opener_for(record)
    destination = tmp_path / "ai-company-run.json"
    preview = exporter.export_from_founder_session(
        "http://127.0.0.1:8000", "secret-session", record["id"], destination,
        opener=io_mock,
    )
    assert preview["mode"] == "preview"
    assert not destination.exists()
    assert len(requests) == 2
    assert all(x[1] == "GET" and x[2] == 15 for x in requests)
    assert all(x[3] == "Bearer secret-session" for x in requests)
    result = exporter.export_from_founder_session(
        "http://127.0.0.1:8000", "secret-session", record["id"], destination,
        apply=True, confirm=exporter.CONFIRM, opener=io_mock,
    )
    assert result["mode"] == "exported_for_offline_source_review"
    raw = destination.read_text()
    assert "PRIVATE FOUNDER TEXT" not in raw
    assert "secret-session" not in raw
    assert "board_recommendations" not in raw
    assert result["tests_executed"] is False
    assert result["independent_qa_approved"] is False
    assert result["github_committed"] is False
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    from ago_engineering_candidate import inspect
    from ago_local_delivery_gate import inspect_local_input
    proposal = inspect(destination)
    assert proposal["candidate_sha256"] == result["candidate_sha256"]
    assert inspect_local_input(destination, None)[1] == "board_record"
    with pytest.raises(FileExistsError):
        exporter.export_from_founder_session(
            "http://127.0.0.1:8000", "secret-session",
            record["id"], destination, apply=True, confirm=exporter.CONFIRM,
            opener=io_mock,
        )


@pytest.mark.parametrize("alter", [
    "not_completed", "missing_board", "unverified_vote", "veto",
    "duplicate_employee", "wrong_task", "tampered_code", "missing_quality",
    "incomplete_roles", "different_run", "unknown_status",
])
def test_denied_incomplete_or_tampered_board_work_cannot_export(
    exporter, tmp_path, alter
):
    record = stored_run()
    result = record["result"]
    if alter == "not_completed":
        record["status"] = "running"
    elif alter == "missing_board":
        result["board_review_cleared"] = False
    elif alter == "unverified_vote":
        result["board_recommendations"][1]["verifiable_model_output"] = False
    elif alter == "veto":
        result["board_recommendations"][3]["recommendation"] = "deny"
    elif alter == "duplicate_employee":
        result["handoffs"][-1]["employee_id"] = result["handoffs"][0]["employee_id"]
    elif alter == "wrong_task":
        result["task_id"] = str(uuid4())
    elif alter == "tampered_code":
        result["engineering_candidate"]["files"][0]["content"] += "# changed"
    elif alter == "missing_quality":
        result["board_recommendations"].pop()
    elif alter == "incomplete_roles":
        result["roles_completed"] = 6
    elif alter == "different_run":
        record["id"] = str(uuid4())
    elif alter == "unknown_status":
        record["status"] = "failed"
    destination = tmp_path / "nope.json"
    with pytest.raises((PermissionError, ValueError)):
        exporter.choose_run([record], str(uuid4()) if alter=="different_run" else record["id"])
    assert not destination.exists()


def test_nonfounder_remote_or_empty_session_blocked_without_writes(exporter, tmp_path):
    record=stored_run()
    destination=tmp_path / "must-not-exist.json"
    nonfounder,_=opener_for(record, founder=False)
    with pytest.raises(PermissionError):
        exporter.export_from_founder_session("http://127.0.0.1:8000","token",
            record["id"], destination, apply=True, confirm=exporter.CONFIRM, opener=nonfounder)
    with pytest.raises(ValueError):
        exporter.export_from_founder_session("https://example.com","token",
            record["id"], destination, opener=nonfounder)
    with pytest.raises(PermissionError):
        exporter.export_from_founder_session("http://127.0.0.1:8000","",
            record["id"], destination, opener=nonfounder)
    assert not destination.exists()


def test_apply_requires_explicit_confirmation_and_never_overwrites(exporter,tmp_path):
    record=stored_run()
    io_mock,_=opener_for(record)
    output=tmp_path/"review.json"
    with pytest.raises(PermissionError):
        exporter.export_from_founder_session("http://127.0.0.1:8000","token",
            record["id"],output,apply=True,opener=io_mock)
    assert not output.exists()
    output.write_text("previous private file")
    with pytest.raises(FileExistsError):
        exporter.export_from_founder_session("http://127.0.0.1:8000","token",
            record["id"],output,apply=True,confirm=exporter.CONFIRM,opener=io_mock)
    assert output.read_text()=="previous private file"


def test_founder_export_refuses_to_put_private_source_inside_git_checkout(
    exporter, monkeypatch, tmp_path
):
    record = stored_run()
    io_mock, _ = opener_for(record)
    source_root = ROOT
    output = source_root / "private_candidate_not_for_git.json"
    with pytest.raises(PermissionError, match="outside the AGO source repository"):
        exporter.export_from_founder_session(
            "http://127.0.0.1:8000", "token", record["id"], output,
            apply=True, confirm=exporter.CONFIRM, opener=io_mock,
        )
    assert not output.exists()
