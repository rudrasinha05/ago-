"""Governed AGO enterprise review proposal; never an automatic GitHub push."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
from uuid import uuid4

import pytest

from test_company_qa_github_handoff import (
    opener_for,
    params,
    setup,
)
from test_company_human_qa_handoff import Reply

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    bridge = importlib.import_module("ago_human_qa_handoff")
    draft_module = importlib.import_module("ago_prepare_github_handoff")
    proposer = importlib.import_module("ago_submit_github_proposal")
    return bridge, draft_module, proposer


def staged_draft(tmp_path, modules):
    bridge, draft_module, proposer = modules
    export, stage, qa, qa_review, _ = setup(tmp_path, (bridge, draft_module))
    remote, _ = opener_for(qa_review)
    draft = tmp_path / "new-github-draft.json"
    draft_module.prepare_draft(
        export, stage, qa, draft, base="http://127.0.0.1:8000",
        token="signed-founder", apply=True, confirm=draft_module.CONFIRM,
        opener=remote, **params(),
    )
    return export, stage, qa, draft, qa_review


def request_mock(qa_review, *, revision=0, uncertain=False, malformed=False):
    calls = []
    def opener(req, timeout=15):
        calls.append((req.get_method(), req.full_url, req.data))
        if req.full_url.endswith("/v1/console/me"):
            return Reply({
                "id": str(uuid4()), "roles": ["founder"],
                "permissions": ["qa:read", "organization:manage"],
            })
        if req.full_url.endswith("/review") and req.get_method() == "GET":
            return Reply(qa_review)
        if req.full_url.endswith("/v1/enterprise/reviews/integration") and req.get_method() == "GET":
            return Reply({"revision": revision, "proposals": []})
        if req.full_url.endswith("/v1/enterprise/reviews/integration/propose") and req.get_method() == "POST":
            if uncertain:
                raise TimeoutError("Simulated pending response after POST")
            data = json.loads(req.data)
            if malformed:
                return Reply({"unexpected": True})
            return Reply({
                "id": str(uuid4()), "approval_id": str(uuid4()),
                "command": "github_operation", "operation_key": data["operation_key"],
            })
        raise AssertionError("Wrong route")
    return opener, calls


def test_verified_qa_and_exact_source_submits_one_immutable_enterprise_proposal(modules,tmp_path):
    _, _, submit_module = modules
    export, stage, qa, draft, record = staged_draft(tmp_path, modules)
    opener, calls = request_mock(record)
    journal = submit_module.DurableAttemptJournal(tmp_path / "claims")
    args = dict(base="http://127.0.0.1:8000", token="signed-founder", opener=opener)
    preview = submit_module.submit(draft,export,stage,qa,**args)
    assert preview["mode"] == "preview"
    assert preview["github_network_called"] is False
    assert preview["approved"] is False
    assert len(calls) == 3 and all(row[0] == "GET" for row in calls)
    assert not (tmp_path / "claims").exists()
    actual = submit_module.submit(
        draft, export, stage, qa, **args,
        apply=True, confirm=submit_module.CONFIRM, journal=journal,
    )
    assert actual["mode"] == "proposal_submitted_for_independent_review"
    assert actual["github_committed"] is False
    assert actual["approved"] is False
    assert len([r for r in calls if r[0] == "POST"]) == 1
    data = json.loads(next(x[2] for x in calls if x[0] == "POST"))
    assert data["command"] == "github_operation"
    assert data["specification"]["operation"] == "commit_files"
    assert data["base_revision"] == 0
    assert "QA-verified" in data["rationale"]
    assert len(list((tmp_path / "claims").glob("*.attempt"))) == 1
    with pytest.raises(FileExistsError):
        submit_module.submit(
            draft, export, stage, qa, **args,
            apply=True, confirm=submit_module.CONFIRM,
            journal=submit_module.DurableAttemptJournal(tmp_path / "claims"),
        )
    assert len([r for r in calls if r[0] == "POST"]) == 1


@pytest.mark.parametrize("bad", [
    "tampered_draft", "changed_head", "failed_qa", "no_confirm",
    "invalid_revision", "missing_journal", "changed_export",
])
def test_no_changed_source_or_qa_or_approval_can_submit(modules,tmp_path,bad):
    _, _, proposer = modules
    export, stage, qa, draft, record = staged_draft(tmp_path,modules)
    if bad in ("tampered_draft", "changed_head"):
        data=json.loads(draft.read_text())
        if bad == "tampered_draft":
            data["github_operation"]["payload"]["files"][0]["content"] += "# changed"
        else:
            data["github_operation"]["payload"]["expected_sha"] = "b"*40
        draft.write_text(json.dumps(data))
    if bad == "failed_qa":
        record["verdict"]="fail"
    if bad == "changed_export":
        export.write_text(export.read_text().replace(
            "ago_authenticated_founder_run", "fake_local_source"))
    opener,calls=request_mock(record,revision=-1 if bad=="invalid_revision" else 0)
    args=dict(
        base="http://127.0.0.1:8000",token="signed-founder",
        opener=opener,apply=True,confirm=proposer.CONFIRM,
        journal=proposer.DurableAttemptJournal(tmp_path / "claims"),
    )
    if bad=="no_confirm":
        args["confirm"]=""
    if bad=="missing_journal":
        args["journal"]=None
    with pytest.raises((PermissionError,ValueError,TypeError,KeyError)):
        proposer.submit(draft,export,stage,qa,**args)
    assert all(x[0] == "GET" for x in calls)


def test_uncertain_post_never_retries_and_never_claims_github_success(modules,tmp_path):
    _,_,proposer=modules
    export,stage,qa,draft,record=staged_draft(tmp_path,modules)
    opener,calls=request_mock(record,uncertain=True)
    claims=tmp_path/"attempts"
    opts=dict(base="http://127.0.0.1:8000",token="signed-founder",
              opener=opener,apply=True,confirm=proposer.CONFIRM)
    with pytest.raises(TimeoutError):
        proposer.submit(draft,export,stage,qa,**opts,
                        journal=proposer.DurableAttemptJournal(claims))
    with pytest.raises(FileExistsError):
        proposer.submit(draft,export,stage,qa,**opts,
                        journal=proposer.DurableAttemptJournal(claims))
    assert len([x for x in calls if x[0] == "POST"])==1
