"""Source-pinned human QA -> safe Section34 GitHub draft, no remote write."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from test_company_human_qa_handoff import fixture as source_fixture
from test_company_human_qa_handoff import Reply

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return (
        importlib.import_module("ago_human_qa_handoff"),
        importlib.import_module("ago_prepare_github_handoff"),
    )


def setup(tmp_path, modules):
    qa_bridge, _ = modules
    export, staged, qa, task_id, candidate = source_fixture(tmp_path, qa_bridge)
    details = qa_bridge.verify_handoff(export, staged, qa)
    reviewer, author = str(uuid4()), str(uuid4())
    prefix = (
        "AGO independent human QA; "
        "run=" + details["run_id"] + "; "
        "project=" + details["project_id"] + "; "
        "candidate_sha256=" + details["candidate_sha256"] + "; "
        "docker_receipt_sha256=" + details["test_receipt_sha256"] + "; "
        "tests=" + str(details["unittest_cases"]) + "; "
        "reviewer_notes=I inspected the implementation and tests independently."
    )
    record = {
        "task_id": task_id, "author_id": author, "reviewer_id": reviewer,
        "verdict": "pass", "evidence": prefix,
    }
    return export, staged, qa, record, candidate


def opener_for(record, *, founder=True):
    calls = []
    def opener(req, timeout=15):
        calls.append((req.get_method(), req.full_url, req.get_header("Authorization")))
        if req.full_url.endswith("/v1/console/me"):
            return Reply({
                "id": str(uuid4()),
                "roles": ["founder"] if founder else ["reviewer"],
                "permissions": ["qa:read", "organization:manage"],
            })
        if req.full_url.endswith("/review"):
            return Reply(record)
        raise AssertionError("Unexpected API call")
    return opener, calls


def params():
    return {
        "github_project_id": str(uuid4()),
        "operation_id": str(uuid4()),
        "expected_sha": "a" * 40,
        "message": "Reviewed AI code and independent human QA",
    }


def test_authenticated_qa_pass_yields_exact_draft_without_github_write(modules, tmp_path):
    _, mod = modules
    export, staged, qa, record, candidate = setup(tmp_path, modules)
    remote, calls = opener_for(record)
    path = tmp_path / "github-draft.json"
    options = params()
    preview = mod.prepare_draft(
        export, staged, qa, path, base="http://127.0.0.1:8000",
        token="signed-founder", opener=remote, **options,
    )
    assert preview["independent_human_qa_verified"] is True
    assert preview["github_write_authorized"] is False
    assert preview["remote_develop_head_verified"] is False
    assert preview["github_committed"] is False
    assert not path.exists()
    saved = mod.prepare_draft(
        export, staged, qa, path, base="http://127.0.0.1:8000",
        token="signed-founder", apply=True, confirm=mod.CONFIRM,
        opener=remote, **options,
    )
    assert saved["github_committed"] is False
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["github_operation"]["operation"] == "commit_files"
    assert result["github_operation"]["payload"]["expected_sha"] == "a" * 40
    assert result["founder_reviewed_expected_sha"] == "a" * 40
    assert result["github_operation"]["payload"]["files"] == candidate["files"]
    assert result["human_qa_verdict"] == "pass"
    assert result["operation_submitted_to_ago"] is False
    assert len(calls) == 4 and all(method == "GET" for method, *_ in calls)
    assert all(header == "Bearer signed-founder" for _, _, header in calls)
    with pytest.raises(PermissionError, match="private output"):
        mod.prepare_draft(
            export, staged, qa, path, base="http://127.0.0.1:8000",
            token="signed-founder", apply=True, confirm=mod.CONFIRM,
            opener=remote, **options,
        )


@pytest.mark.parametrize("alter", [
    "failed_qa", "wrong_digest", "self_review", "wrong_task",
    "missing_notes", "wrong_reviewer_role", "bad_head", "missing_confirmation",
    "tampered_source", "tampered_qa",
])
def test_no_source_or_qa_bypass_can_prepare_github_draft(modules, tmp_path, alter):
    _, mod = modules
    export, staged, qa, record, _ = setup(tmp_path, modules)
    if alter == "failed_qa":
        record["verdict"] = "fail"
    elif alter == "wrong_digest":
        record["evidence"] = record["evidence"].replace(
            "candidate_sha256=", "candidate_sha256=" + "f" * 64 + "-")
    elif alter == "self_review":
        record["reviewer_id"] = record["author_id"]
    elif alter == "wrong_task":
        record["task_id"] = str(uuid4())
    elif alter == "missing_notes":
        record["evidence"] = record["evidence"].split("reviewer_notes=")[0] + "reviewer_notes=x"
    elif alter == "tampered_source":
        original = json.loads(export.read_text())
        original["result"]["engineering_candidate"]["files"][0]["content"] += "# tamper"
        export.write_text(json.dumps(original), encoding="utf-8")
    elif alter == "tampered_qa":
        saved = json.loads(qa.read_text())
        saved["qa_approved"] = True
        qa.write_text(json.dumps(saved))
    remote, calls = opener_for(record, founder=alter != "wrong_reviewer_role")
    opts = params()
    if alter == "bad_head":
        opts["expected_sha"] = "not-a-real-hash"
    kwargs = dict(
        base="http://127.0.0.1:8000", token="signed-founder",
        apply=True, confirm=mod.CONFIRM, opener=remote, **opts,
    )
    if alter == "missing_confirmation":
        kwargs["confirm"] = ""
    output = tmp_path / "blocked-git.json"
    with pytest.raises((ValueError, TypeError, PermissionError)):
        mod.prepare_draft(export, staged, qa, output, **kwargs)
    assert not output.exists()
    assert all(method == "GET" for method, _, _ in calls)


def test_no_github_operations_or_unreviewed_source_are_exported(modules, tmp_path):
    _, mod = modules
    export, staged, qa, record, _ = setup(tmp_path, modules)
    remote, calls = opener_for(record)
    with pytest.raises(PermissionError):
        mod.prepare_draft(
            export, staged, qa, ROOT / "should-not-exist.json",
            base="http://127.0.0.1:8000", token="signed-founder",
            apply=True, confirm=mod.CONFIRM, opener=remote, **params(),
        )
    assert all(method == "GET" for method, _, _ in calls)
