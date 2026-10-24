"""Source-backed approved commit + strict CI -> governed draft PR with no auto merge."""
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
def setup(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    bridge = importlib.import_module("ago_human_qa_handoff")
    draft_lib = importlib.import_module("ago_prepare_github_handoff")
    proposal_lib = importlib.import_module("ago_submit_github_proposal")
    pr = importlib.import_module("ago_draft_pull_request")
    export, stage, qa, commit_draft, qa_review = staged_draft(
        tmp_path, (bridge, draft_lib, proposal_lib),
    )
    original = json.loads(commit_draft.read_text())["github_operation"]
    commit_proposal = str(uuid4())
    pr_proposal = str(uuid4())
    founder = str(uuid4())
    pr_op_id = str(uuid4())
    project_id = original["project_id"]
    checks = ["Backend QA", "Browser QA"]
    calls = []
    state = {"ci": "success", "visibility": True, "prior_pr": False,
             "commit_status": "succeeded", "pr_approved": True,
             "pr_applied": True, "uncertain": False, "pr_record": None}

    def mock(req, timeout=20):
        calls.append((req.get_method(), req.full_url, req.data))
        if req.full_url.endswith("/v1/console/me"):
            return Reply({"id": founder, "roles": ["founder"],
                          "permissions": ["qa:read", "organization:manage"]})
        if req.full_url.endswith("/review"):
            return Reply(qa_review)
        if req.full_url.endswith("/v1/platform/catalog"):
            rows = [{
                "id": original["id"], "kind": "github_operation",
                "payload": original, "proposal_id": commit_proposal,
            }]
            if state["pr_applied"] and state["pr_record"] is not None:
                rows.append({
                    "id": pr_op_id, "kind": "github_operation",
                    "payload": state["pr_record"]["operation"],
                    "proposal_id": pr_proposal,
                })
            return Reply({"github_operations": rows})
        if req.full_url.endswith("/status"):
            runs = [{
                "name": name, "status": "completed",
                "conclusion": "success",
            } for name in checks]
            if state["ci"] == "pending":
                runs[0]["status"] = "in_progress"
            if state["ci"] == "failed":
                runs[0]["conclusion"] = "failure"
            if state["ci"] == "duplicate":
                runs.append(dict(runs[0]))
            if state["ci"] == "missing":
                runs.pop(0)
            operations = [{
                "operation_id": original["id"],
                "status": state["commit_status"],
                "result": {"sha": "c" * 40},
            }]
            if state["prior_pr"]:
                operations.append({"operation_id": pr_op_id, "status": "uncertain"})
            return Reply({
                "project_id": project_id,
                "repository": "rudrasinha05/private-project",
                "repository_private": state["visibility"],
                "develop_sha": "c" * 40,
                "ci": runs, "ci_total": len(runs), "ci_truncated": False,
                "operations": operations,
            })
        if req.full_url.endswith("/v1/enterprise/reviews/integration"):
            proposals = []
            if state["pr_record"] is not None:
                proposals.append({
                    "id": pr_proposal, "domain": "integration",
                    "command": "github_operation",
                    "status": "approved" if state["pr_approved"] else "pending",
                    "actor_id": founder, "approval_id": str(uuid4()),
                    "operation_key": pr_op_id,
                    "specification": state["pr_record"]["operation"],
                })
            return Reply({"revision": 8, "proposals": proposals})
        if req.full_url.endswith("/propose"):
            if state["uncertain"]:
                raise TimeoutError("Uncertain PR proposal")
            return Reply({
                "id": pr_proposal, "approval_id": str(uuid4()),
                "command": "github_operation", "operation_key": pr_op_id,
            })
        if req.full_url.endswith("/apply"):
            if state["uncertain"]:
                raise TimeoutError("Uncertain approved apply")
            return Reply({
                "proposal_id": pr_proposal,
                "result": {"id": pr_op_id, "kind": "github_operation"},
            })
        if req.full_url.endswith("/execute"):
            if state["uncertain"]:
                raise TimeoutError("Uncertain GitHub PR write")
            return Reply({
                "operation_id": pr_op_id, "status": "succeeded",
                "result": {
                    "number": 4, "head_sha": "c" * 40,
                    "url": "https://github.com/rudrasinha05/private-project/pull/4",
                },
            })
        raise AssertionError("unexpected endpoint: " + req.full_url)

    args = dict(
        commit_proposal=commit_proposal, base="http://127.0.0.1:8000",
        token="signed-founder", opener=mock,
    )
    files = (commit_draft, export, stage, qa, tmp_path / "draft-pr.json")
    return pr, files, state, calls, args, checks, pr_op_id


def prepare(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    values = dict(phase="prepare", operation_id=pr_id,
                  title="Verified AI project", body="Independent human QA and CI evidence",
                  checks=checks)
    result = pr.deliver(*files, **args, **values, apply=True,
                        confirm=pr.CONFIRMS["prepare"])
    assert result["private_draft_saved"] is True
    state["pr_record"] = json.loads(files[4].read_text())
    return state["pr_record"]


def test_local_ci_is_strict_and_blocks_failed_pending_duplicate_or_public(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    for condition in ("pending", "failed", "missing", "duplicate"):
        state["ci"] = condition
        with pytest.raises(PermissionError):
            pr.deliver(*files, **args, phase="prepare",
                       operation_id=pr_id, title="Code", body="QA",
                       checks=checks)
    state["ci"] = "success"
    state["visibility"] = False
    with pytest.raises(PermissionError):
        pr.deliver(*files, **args, phase="prepare",
                   operation_id=pr_id, title="Code", body="QA", checks=checks)
    assert not files[4].exists()
    assert all(method == "GET" for method, _, _ in calls)


def test_verified_commit_and_ci_make_private_pr_draft_without_network_write(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    record = prepare(setup)
    assert record["kind"] == "ago_ci_verified_draft_pr"
    assert record["operation"]["operation"] == "create_pull_request"
    assert record["operation"]["payload"]["expected_sha"] == "c" * 40
    assert record["operation"]["payload"]["required_checks"] == checks
    assert record["merge_authorized"] is False
    assert record["release_ready"] is False
    assert all(method == "GET" for method, _, _ in calls)


def test_mutated_pr_or_source_cannot_enter_governance(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    record = prepare(setup)
    record["operation"]["payload"]["title"] = "Switched project"
    files[4].write_text(json.dumps(record))
    with pytest.raises(PermissionError):
        pr.deliver(*files, **args, phase="submit")
    assert all(method == "GET" for method, _, _ in calls)


def test_missing_real_github_commit_never_creates_pr(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    state["commit_status"] = "uncertain"
    with pytest.raises(PermissionError):
        pr.deliver(*files, **args, phase="prepare",
                   operation_id=pr_id, title="Project", body="Reviewed",
                   checks=checks)
    assert not files[4].exists()


def test_pr_schema_and_required_ci_reject_unbounded_or_fake_checks(setup):
    pr, files, state, calls, args, checks, pr_id = setup
    for item in ([], ["same", "same"], [""]):
        with pytest.raises(ValueError):
            pr.deliver(*files, **args, phase="prepare",
                       operation_id=pr_id, title="Review", body="QA", checks=item)
    assert not files[4].exists()


def test_distinct_founder_approval_proposal_then_apply_then_real_draft_pr(setup, tmp_path):
    pr, files, state, calls, args, checks, pr_id = setup
    prepare(setup)
    claims = pr.DurableAttemptJournal(tmp_path / "claims")
    preview = pr.deliver(*files, **args, phase="submit")
    assert preview["github_pr_created"] is False
    assert all(method == "GET" for method, *_ in calls)
    proposed = pr.deliver(*files, **args, phase="submit", apply=True,
                          confirm=pr.CONFIRMS["submit"], journal=claims)
    assert proposed["pr_proposal_id"]
    assert proposed["github_pr_created"] is False
    pr_proposal = proposed["pr_proposal_id"]
    with pytest.raises(FileExistsError):
        pr.deliver(*files, **args, phase="submit", apply=True,
                   confirm=pr.CONFIRMS["submit"], journal=claims)
    preview_apply = pr.deliver(*files, **args, phase="apply", pr_proposal=pr_proposal)
    assert preview_apply["github_pr_created"] is False
    applied = pr.deliver(
        *files, **args, phase="apply", pr_proposal=pr_proposal, apply=True,
        confirm=pr.CONFIRMS["apply"], journal=claims,
    )
    assert applied["governance_applied"] is True
    assert applied["github_pr_created"] is False
    preview_exec = pr.deliver(*files, **args, phase="execute",
                              pr_proposal=pr_proposal)
    assert preview_exec["github_pr_created"] is False
    completed = pr.deliver(
        *files, **args, phase="execute", pr_proposal=pr_proposal,
        apply=True, confirm=pr.CONFIRMS["execute"], journal=claims,
    )
    assert completed["github_pr_created"] is True
    assert completed["draft_pr_number"] == 4
    assert completed["draft_pr_url"].endswith("/private-project/pull/4")
    assert completed["merge_authorized"] is False
    assert completed["release_ready"] is False
    assert len([x for x in calls if x[0] == "POST"]) == 3
    with pytest.raises(FileExistsError):
        pr.deliver(*files, **args, phase="execute", pr_proposal=pr_proposal,
                   apply=True, confirm=pr.CONFIRMS["execute"], journal=claims)
    assert len([x for x in calls if x[0] == "POST"]) == 3


@pytest.mark.parametrize("failed", ["unapproved", "not_applied", "previous", "pending_ci"])
def test_pr_execution_refuses_missing_independent_acceptance(setup, tmp_path, failed):
    pr, files, state, calls, args, checks, pr_id = setup
    prepare(setup)
    proposal = str(uuid4())
    if failed == "unapproved":
        state["pr_approved"] = False
    if failed == "not_applied":
        state["pr_applied"] = False
    if failed == "previous":
        state["prior_pr"] = True
    if failed == "pending_ci":
        state["ci"] = "pending"
    with pytest.raises(PermissionError):
        pr.deliver(
            *files, **args, phase="execute", pr_proposal=proposal, apply=True,
            confirm=pr.CONFIRMS["execute"],
            journal=pr.DurableAttemptJournal(tmp_path / "claims"),
        )
    assert all(method == "GET" for method, *_ in calls)
    assert not (tmp_path / "claims").exists()


@pytest.mark.parametrize("phase", ["submit", "apply", "execute"])
def test_uncertain_submission_is_never_replayed(setup, tmp_path, phase):
    pr, files, state, calls, args, checks, pr_id = setup
    prepare(setup)
    state["uncertain"] = True
    claims = tmp_path / "claims"
    proposal = str(uuid4())
    kwargs = dict(phase=phase, pr_proposal=proposal, apply=True,
                  confirm=pr.CONFIRMS[phase])
    with pytest.raises(TimeoutError):
        pr.deliver(*files, **args, **kwargs,
                   journal=pr.DurableAttemptJournal(claims))
    with pytest.raises(FileExistsError):
        pr.deliver(*files, **args, **kwargs,
                   journal=pr.DurableAttemptJournal(claims))
    assert len([m for m, *_ in calls if m == "POST"]) == 1
