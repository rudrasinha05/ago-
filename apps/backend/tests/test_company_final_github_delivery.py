"""Approved AGO proposal -> independently authorized apply and GitHub dispatch."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from test_company_human_qa_handoff import Reply
from test_company_qa_github_proposal import staged_draft

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return (
        importlib.import_module("ago_human_qa_handoff"),
        importlib.import_module("ago_prepare_github_handoff"),
        importlib.import_module("ago_submit_github_proposal"),
        importlib.import_module("ago_finalize_github_delivery"),
    )


def setup(tmp_path, modules):
    bridge, draft_module, proposal_module, _ = modules
    export, stage, qa, draft, review = staged_draft(
        tmp_path, (bridge, draft_module, proposal_module)
    )
    row = json.loads(draft.read_text())
    # Operator signature is (draft, source, staged, qa_packet).
    return draft, export, stage, qa, review, row


def mock_server(record, draft, *, mutate=None, uncertain=False):
    founder = str(uuid4())
    approval = str(uuid4())
    proposal_id = str(uuid4())
    operation = draft["github_operation"]
    project_id = operation["project_id"]
    expected_sha = operation["payload"]["expected_sha"]
    calls = []
    proposal = {
        "id": proposal_id, "domain": "integration",
        "command": "github_operation", "status": "approved",
        "actor_id": founder, "approval_id": approval,
        "operation_key": operation["id"], "specification": operation,
    }
    applied = {
        "kind": "github_operation", "id": operation["id"],
        "proposal_id": proposal_id, "payload": operation,
    }
    status = {
        "project_id": project_id,
        "repository_private": True,
        "develop_sha": expected_sha,
        "operations": [],
    }
    if mutate == "unapproved":
        proposal["status"] = "pending"
    if mutate == "wrong_proposal":
        proposal["specification"] = {**operation, "id": str(uuid4())}
    if mutate == "different_founder":
        proposal["actor_id"] = str(uuid4())
    if mutate == "not_applied":
        applied["proposal_id"] = str(uuid4())
    if mutate == "changed_head":
        status["develop_sha"] = "b" * 40
    if mutate == "public_repo":
        status["repository_private"] = False
    if mutate == "previous_dispatch":
        status["operations"] = [{"operation_id": operation["id"], "status": "uncertain"}]
    if mutate == "failed_qa":
        record["verdict"] = "fail"

    def opener(req, timeout=15):
        calls.append((req.get_method(), req.full_url, req.data))
        if req.full_url.endswith("/v1/console/me"):
            return Reply({
                "id": founder, "roles": ["founder"],
                "permissions": ["qa:read", "approval:decide", "organization:manage"],
            })
        if req.full_url.endswith("/review"):
            return Reply(record)
        if req.full_url.endswith("/v1/enterprise/reviews/integration"):
            return Reply({"revision": 0, "proposals": [proposal]})
        if req.full_url.endswith("/v1/platform/catalog"):
            return Reply({"github_operations": [applied]})
        if req.full_url.endswith("/status"):
            return Reply(status)
        if req.full_url.endswith("/v1/enterprise/reviews/integration/apply"):
            if uncertain:
                raise TimeoutError("May already have applied to AGO")
            return Reply({
                "proposal_id": proposal_id,
                "result": {"id": operation["id"], "kind": "github_operation"},
            })
        if req.full_url.endswith("/execute"):
            if uncertain:
                raise TimeoutError("May already have reached GitHub")
            return Reply({
                "operation_id": operation["id"], "status": "succeeded",
                "result": {"sha": "c" * 40, "tree": "d" * 40},
            })
        raise AssertionError("Unexpected API path")

    return opener, calls, proposal_id


def test_apply_is_independently_approved_no_github_network(modules, tmp_path):
    *files, human_review, draft = setup(tmp_path, modules)
    operator = modules[-1]
    opener, calls, proposal_id = mock_server(human_review, draft)
    args = dict(base="http://127.0.0.1:8000", token="signed-founder",
                proposal_id=proposal_id, opener=opener)
    preview = operator.verified_delivery(*files, action="apply", **args)
    assert preview["mode"] == "preview"
    assert preview["github_committed"] is False
    assert all(method == "GET" for method, _, _ in calls)
    journal = operator.DurableAttemptJournal(tmp_path / "attempts")
    result = operator.verified_delivery(
        *files, action="apply", apply=True, confirm=operator.APPLY_CONFIRM,
        journal=journal, **args,
    )
    assert result["governance_applied"] is True
    assert result["github_committed"] is False
    assert result["remote_write_attempted"] is False
    assert [url for method, url, _ in calls if method == "POST"] == [
        "http://127.0.0.1:8000/v1/enterprise/reviews/integration/apply"
    ]
    with pytest.raises(FileExistsError):
        operator.verified_delivery(
            *files, action="apply", apply=True, confirm=operator.APPLY_CONFIRM,
            journal=operator.DurableAttemptJournal(tmp_path / "attempts"), **args,
        )
    assert len([method for method, *_ in calls if method == "POST"]) == 1


def test_execute_requires_applied_exact_head_and_returns_real_sha(modules, tmp_path):
    *files, human_review, draft = setup(tmp_path, modules)
    operator = modules[-1]
    opener, calls, proposal_id = mock_server(human_review, draft)
    kwargs = dict(base="http://127.0.0.1:8000", token="signed-founder",
                  proposal_id=proposal_id, opener=opener)
    preview = operator.verified_delivery(*files, action="execute", **kwargs)
    assert preview["remote_develop_head_verified"] is True
    assert preview["github_committed"] is False
    assert all(method == "GET" for method, *_ in calls)
    result = operator.verified_delivery(
        *files, action="execute", apply=True, confirm=operator.EXECUTE_CONFIRM,
        journal=operator.DurableAttemptJournal(tmp_path / "attempts"), **kwargs,
    )
    assert result["github_committed"] is True
    assert result["committed_sha"] == "c" * 40
    assert result["release_ready"] is False
    assert len([method for method, *_ in calls if method == "POST"]) == 1
    assert calls[-1][1].endswith(
        "/v1/platform/github/operations/" + draft["github_operation"]["id"] + "/execute"
    )
    with pytest.raises(FileExistsError):
        operator.verified_delivery(
            *files, action="execute", apply=True, confirm=operator.EXECUTE_CONFIRM,
            journal=operator.DurableAttemptJournal(tmp_path / "attempts"), **kwargs,
        )
    assert len([method for method, *_ in calls if method == "POST"]) == 1


@pytest.mark.parametrize("bad", [
    "unapproved", "wrong_proposal", "different_founder", "not_applied",
    "changed_head", "public_repo", "previous_dispatch", "failed_qa",
])
def test_no_wrong_review_or_changed_source_can_execute(modules, tmp_path, bad):
    *files, review, draft = setup(tmp_path, modules)
    operator = modules[-1]
    opener, calls, pid = mock_server(review, draft, mutate=bad)
    journal = operator.DurableAttemptJournal(tmp_path / "claims")
    with pytest.raises((PermissionError, ValueError)):
        operator.verified_delivery(
            *files, base="http://127.0.0.1:8000", token="founder",
            proposal_id=pid, action="execute", apply=True,
            confirm=operator.EXECUTE_CONFIRM, journal=journal, opener=opener,
        )
    assert all(method == "GET" for method, *_ in calls)
    assert not (tmp_path / "claims").exists()


def test_missing_confirmation_never_applies_or_executes(modules, tmp_path):
    *files, review, draft = setup(tmp_path, modules)
    operator = modules[-1]
    opener, calls, pid = mock_server(review, draft)
    with pytest.raises(PermissionError):
        operator.verified_delivery(
            *files, base="http://127.0.0.1:8000", token="founder",
            proposal_id=pid, action="execute", apply=True, opener=opener,
        )
    assert all(method == "GET" for method, *_ in calls)


@pytest.mark.parametrize("phase", ["apply", "execute"])
def test_uncertain_network_result_is_never_replayed(modules, tmp_path, phase):
    *files, review, draft = setup(tmp_path, modules)
    operator = modules[-1]
    opener, calls, pid = mock_server(review, draft, uncertain=True)
    args = dict(base="http://127.0.0.1:8000", token="founder",
                proposal_id=pid, action=phase, apply=True,
                confirm=operator.APPLY_CONFIRM if phase == "apply" else operator.EXECUTE_CONFIRM,
                opener=opener)
    with pytest.raises(TimeoutError):
        operator.verified_delivery(
            *files, journal=operator.DurableAttemptJournal(tmp_path / "claims"),
            **args,
        )
    with pytest.raises(FileExistsError):
        operator.verified_delivery(
            *files, journal=operator.DurableAttemptJournal(tmp_path / "claims"),
            **args,
        )
    assert len([method for method, *_ in calls if method == "POST"]) == 1


def test_host_restrictions_and_unexpected_endpoint_are_fail_closed(modules):
    op=modules[-1]
    with pytest.raises((ValueError, PermissionError)):
        op.read_local("https://example.com", "token", "/v1/console/me")
    with pytest.raises(PermissionError):
        op.post_local("http://127.0.0.1:8000", "token",
                      "/v1/platform/github/pulls/1/merge", {})
