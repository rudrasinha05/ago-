"""Local Docker evidence -> independent authenticated human QA, never synthetic PASS."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from ago.company_engineering import reviewed_candidate, stage_candidate

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def bridge(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return importlib.import_module("ago_human_qa_handoff")


def fixture(tmp_path, bridge):
    candidate = reviewed_candidate(json.dumps({
        "files": [
            {"path": "src/example.py", "content": "def twice(n):\n    return n * 2\n"},
            {"path": "tests/test_example.py",
             "content": ("import unittest\nfrom src.example import twice\n"
                         "class T(unittest.TestCase):\n"
                         "    def test_twice(self):\n"
                         "        self.assertEqual(twice(3),6)\n")},
        ],
        "acceptance_checks": ["Twice 3 is 6 and human source review required"],
    }))
    stage = tmp_path / "stage"
    stage_candidate(candidate, stage)
    receipt = {
        "kind": "ago_local_container_unittest_receipt",
        "candidate_sha256": candidate["candidate_sha256"],
        "tests_executed": True, "tests_passed": True,
        "unittest_cases": 1, "docker_exit_code": 0,
        "network_disabled": True, "read_only_container": True,
        "git_committed": False, "independent_qa_approved": False,
        "release_ready": False,
    }
    (stage / "AGO_TEST_RECEIPT.json").write_text(json.dumps(receipt))
    qa = tmp_path / "qa.json"
    qa.write_text(json.dumps(bridge.packet(stage)))
    task_id, run_id, project_id = (str(uuid4()) for _ in range(3))
    export = tmp_path / "source-export.json"
    export.write_text(json.dumps({
        "source": "ago_authenticated_founder_run",
        "id": run_id, "task_id": task_id, "project_id": project_id,
        "status": "completed",
        "result": {
            "board_review_cleared": True,
            "engineering_candidate": candidate,
        },
    }))
    return export, stage, qa, task_id, candidate


class Reply:
    def __init__(self, value):
        self.raw = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, maximum):
        return self.raw[:maximum]


def web_mock(task_id, *, reviewer=None, worker=None, permission=True, present=True,
             fail_post=False):
    reviewer = reviewer or str(uuid4())
    worker = worker or str(uuid4())
    calls = []
    def open_request(req, timeout=15):
        calls.append((req.full_url, req.get_method(), req.get_header("Authorization")))
        if req.full_url.endswith("/v1/console/me"):
            return Reply({
                "id": reviewer,
                "roles": ["reviewer"],
                "permissions": ["qa:read", "qa:review"] if permission else ["qa:read"],
            })
        if req.full_url.endswith("/v1/console/qa-queue"):
            return Reply([{
                "id": task_id, "status": "completed", "assignee_id": worker,
            }] if present else [])
        if req.full_url.endswith("/review") and req.get_method() == "POST":
            if fail_post:
                raise TimeoutError("Simulated uncertain server response")
            payload = json.loads(req.data)
            return Reply({
                "artifact_id": task_id, "reviewer_id": reviewer,
                "verdict": payload["verdict"], "evidence": payload["evidence"],
            })
        raise AssertionError("Unexpected endpoint: " + req.full_url)
    return open_request, calls, reviewer


def test_review_uses_exact_real_task_docker_source_and_authenticated_human(
    bridge, tmp_path
):
    export, stage, qa, task_id, candidate = fixture(tmp_path, bridge)
    opener, calls, reviewer = web_mock(task_id)
    details = dict(
        verdict="pass", notes="I inspected original tests and isolated Docker evidence.",
        opener=opener,
    )
    preview = bridge.review_from_session(
        "http://127.0.0.1:8000", "private-token", export, stage, qa, **details,
    )
    assert preview["mode"] == "review_preview"
    assert preview["candidate_sha256"] == candidate["candidate_sha256"]
    assert preview["independent_human_qa_recorded"] is False
    assert len(calls) == 2 and all(method == "GET" for _, method, _ in calls)
    assert not (tmp_path / "attempts").exists()
    journal = bridge.DurableAttemptJournal(tmp_path / "attempts")
    posted = bridge.review_from_session(
        "http://127.0.0.1:8000", "private-token", export, stage, qa, **details,
        apply=True, confirm=bridge.CONFIRM, journal=journal,
    )
    assert posted["independent_human_qa_recorded"] is True
    assert posted["reviewer_id"] == reviewer
    assert posted["verdict"] == "pass"
    assert posted["github_write_authorized"] is False
    assert posted["release_ready"] is False
    assert len([x for x in calls if x[1] == "POST"]) == 1
    assert len(list((tmp_path / "attempts").glob("*.attempt"))) == 1
    with pytest.raises(FileExistsError, match="previously attempted"):
        bridge.review_from_session(
            "http://127.0.0.1:8000", "private-token", export, stage, qa,
            **details, apply=True, confirm=bridge.CONFIRM, journal=journal,
        )
    assert len([x for x in calls if x[1] == "POST"]) == 1


@pytest.mark.parametrize("failure", [
    "tamper_qa", "tamper_code", "tamper_receipt", "wrong_source",
    "no_review_permission", "self_review", "not_in_queue",
    "no_confirmation", "no_journal",
])
def test_non_authoritative_or_unsafe_QA_never_posts(bridge, tmp_path, failure):
    export, stage, qa, task_id, _ = fixture(tmp_path, bridge)
    reviewer = str(uuid4())
    kwargs = {"reviewer": reviewer}
    if failure == "tamper_qa":
        saved = json.loads(qa.read_text())
        saved["qa_approved"] = True
        qa.write_text(json.dumps(saved))
    if failure == "tamper_code":
        (stage / "src/example.py").write_text("def twice(n): return 0\n")
    if failure == "tamper_receipt":
        path = stage / "AGO_TEST_RECEIPT.json"
        receipt = json.loads(path.read_text())
        receipt["tests_passed"] = False
        path.write_text(json.dumps(receipt))
    if failure == "wrong_source":
        saved = json.loads(export.read_text())
        saved["source"] = "fake_local_receipt"
        export.write_text(json.dumps(saved))
    if failure == "no_review_permission":
        kwargs["permission"] = False
    if failure == "self_review":
        kwargs["worker"] = reviewer
    if failure == "not_in_queue":
        kwargs["present"] = False
    opener, calls, _ = web_mock(task_id, **kwargs)
    args = dict(
        verdict="pass", notes="Verified separate human QA review with source evidence.",
        apply=True, confirm=bridge.CONFIRM,
        journal=bridge.DurableAttemptJournal(tmp_path / "attempts"),
        opener=opener,
    )
    if failure == "no_confirmation":
        args["confirm"] = ""
    if failure == "no_journal":
        args["journal"] = None
    with pytest.raises((PermissionError, ValueError)):
        bridge.review_from_session(
            "http://127.0.0.1:8000", "private-token", export, stage, qa, **args,
        )
    assert not any(method == "POST" for _, method, _ in calls)


def test_review_timeout_is_no_replay_across_later_processes(bridge, tmp_path):
    export, stage, qa, task_id, _ = fixture(tmp_path, bridge)
    opener, calls, _ = web_mock(task_id, fail_post=True)
    journal = bridge.DurableAttemptJournal(tmp_path / "attempts")
    args = dict(verdict="fail", notes="Human identified a functional mismatch.",
                apply=True, confirm=bridge.CONFIRM, journal=journal, opener=opener)
    with pytest.raises(TimeoutError):
        bridge.review_from_session(
            "http://127.0.0.1:8000", "private-token", export, stage, qa, **args,
        )
    assert len([x for x in calls if x[1] == "POST"]) == 1
    with pytest.raises(FileExistsError):
        bridge.review_from_session(
            "http://127.0.0.1:8000", "private-token", export, stage, qa,
            **{**args, "journal": bridge.DurableAttemptJournal(tmp_path / "attempts")},
        )
    assert len([x for x in calls if x[1] == "POST"]) == 1


def test_invalid_server_and_missing_notes_cannot_make_QA_verdict(bridge, tmp_path):
    export, stage, qa, task_id, _ = fixture(tmp_path, bridge)
    opener, calls, _ = web_mock(task_id)
    for host in ("https://example.com", "http://192.0.2.1:8000"):
        with pytest.raises(ValueError):
            bridge.review_from_session(
                host, "token", export, stage, qa, verdict="pass",
                notes="Reviewed all source and passing Docker evidence", opener=opener,
            )
    with pytest.raises(ValueError):
        bridge.review_from_session(
            "http://127.0.0.1:8000", "token", export, stage, qa, verdict="pass",
            notes="", opener=opener,
        )
    assert calls == []
