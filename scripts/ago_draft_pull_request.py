"""AGO verified commit -> independently governed DRAFT GitHub PR.

Never merges, releases, or replays uncertain writes. Original human QA,
committed SHA and all required CI are checked before every phase; the server
GitHub adapter independently rechecks named CI at PR dispatch.
"""
from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import re
import sys
from pathlib import Path
from uuid import UUID, uuid5

from ago.github_adapter import validate_operation
from ago_finalize_github_delivery import (
    checked_applied,
    checked_review,
    post_local,
    read_local,
)
from ago_human_qa_handoff import LOCAL_OPENER, read_document
from ago_submit_github_proposal import enterprise_call, inspect_verified_draft
from local_approved_agent_batch import DurableAttemptJournal, founder_login, local_url

CONFIRMS = {
    "prepare": "PREPARE_VERIFIED_DRAFT_PR",
    "submit": "SUBMIT_VERIFIED_DRAFT_PR",
    "apply": "APPLY_APPROVED_DRAFT_PR",
    "execute": "CREATE_APPROVED_DRAFT_PR",
}


def ci_gate(status, sha, checks):
    if (not isinstance(checks, list) or not 1 <= len(checks) <= 24
            or any(not isinstance(c, str) or not 1 <= len(c) <= 120 for c in checks)
            or len(set(checks)) != len(checks)):
        raise ValueError("Unique exact GitHub CI check names required")
    if (not isinstance(status, dict) or status.get("develop_sha") != sha
            or status.get("repository_private") is not True
            or status.get("ci_truncated") is not False
            or status.get("ci_check_truncated") is not False
            or status.get("ci_status_truncated") is not False
            or not isinstance(status.get("ci_check_runs"), list)
            or not isinstance(status.get("ci_statuses"), list)
            or type(status.get("ci_check_total")) is not int
            or status["ci_check_total"] != len(status["ci_check_runs"])):
        raise PermissionError("Private exact HEAD and complete provider CI needed")
    for name in checks:
        verdicts = [
            c.get("status") == "completed" and c.get("conclusion") == "success"
            for c in status["ci_check_runs"]
            if isinstance(c, dict) and c.get("name") == name
        ]
        verdicts.extend(
            c.get("state") == "success"
            for c in status["ci_statuses"]
            if isinstance(c, dict) and c.get("context") == name
        )
        if len(verdicts) != 1 or verdicts[0] is not True:
            raise PermissionError("Required CI check missing, failed or ambiguous")


def commit_proof(commit_draft, export, stage, qa, commit_proposal, checks,
                 base, token, opener=LOCAL_OPENER):
    UUID(commit_proposal)
    verified = inspect_verified_draft(
        commit_draft, export, stage, qa, base=base, token=token, opener=opener,
    )
    commit = verified["operation"]
    catalog = read_local(base, token, "/v1/platform/catalog", opener=opener)
    checked_applied(commit, commit_proposal, catalog)
    status = read_local(
        base, token, "/v1/platform/github/projects/" + commit["project_id"]
        + "/status", opener=opener,
    )
    if (not isinstance(status, dict)
            or status.get("project_id") != commit["project_id"]
            or status.get("repository_private") is not True
            or not isinstance(status.get("operations"), list)
            or not isinstance(status.get("repository"), str)
            or not status["repository"].startswith("rudrasinha05/")):
        raise PermissionError("Exact private bound GitHub project required")
    rows = [x for x in status["operations"] if isinstance(x, dict)
            and str(x.get("operation_id")) == commit["id"]]
    if (len(rows) != 1 or rows[0].get("status") != "succeeded"
            or not isinstance(rows[0].get("result"), dict)):
        raise PermissionError("Real AGO-created commit receipt is required")
    sha = rows[0]["result"].get("sha")
    if not isinstance(sha, str) or not re.fullmatch("[a-f0-9]{40}", sha):
        raise PermissionError("Exact real committed SHA required")
    ci_gate(status, sha, checks)
    return {"committed_sha": sha, "project_id": commit["project_id"],
            "repository": status["repository"],
            "commit_operation": commit["id"],
            "commit_proposal": commit_proposal,
            "qa_sha": verified["qa"]["candidate_sha256"],
            "qa_reviewer": verified["qa"]["qa_reviewer_id"]}


def canonical_record(op, proof):
    value = {"kind": "ago_ci_verified_draft_pr",
             "operation": op, "original_commit": proof,
             "checks": op["payload"]["required_checks"],
             "draft": True, "merge_authorized": False, "release_ready": False}
    value["digest"] = hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return value


def deliver(commit_draft, export, stage, qa, pr_draft, *, phase,
            commit_proposal, base, token, checks=None, operation_id="",
            title="", body="", pr_proposal="", apply=False, confirm="",
            journal=None, opener=LOCAL_OPENER):
    if phase not in CONFIRMS:
        raise ValueError("Supported PR stage required")
    if apply and (confirm != CONFIRMS[phase]
                  or (phase != "prepare" and journal is None)):
        raise PermissionError("Phase confirmation and no-replay claim required")
    saved = None
    if phase != "prepare":
        saved = read_document(pr_draft, max_bytes=26000)
        checks = saved.get("checks")
    proof = commit_proof(
        commit_draft, export, stage, qa, commit_proposal,
        checks, base, token, opener=opener,
    )
    me = read_local(base, token, "/v1/console/me", opener=opener)
    if not isinstance(me, dict) or "founder" not in me.get("roles", []):
        raise PermissionError("Signed original Founder session required")
    if phase == "prepare":
        op = {"id": str(UUID(operation_id)), "project_id": proof["project_id"],
              "operation": "create_pull_request",
              "payload": {"expected_sha": proof["committed_sha"], "title": title,
                          "body": body, "required_checks": checks}}
        validate_operation(op)
        record = canonical_record(op, proof)
    else:
        op = saved.get("operation")
        if not isinstance(op, dict):
            raise TypeError("Verified original PR draft required")
        validate_operation(op)
        if (op.get("operation") != "create_pull_request"
                or op.get("project_id") != proof["project_id"]
                or op["payload"].get("expected_sha") != proof["committed_sha"]
                or saved != canonical_record(op, proof)):
            raise PermissionError("Saved Founder-reviewed PR has changed")
    report = {"phase": phase, "operation_id": op["id"],
              "commit_sha": proof["committed_sha"], "checks": checks,
              "github_pr_created": False, "merge_authorized": False,
              "release_ready": False}
    if phase == "prepare":
        if apply:
            root = Path(__file__).resolve().parents[1]
            if (pr_draft.resolve().is_relative_to(root) or pr_draft.exists()
                    or pr_draft.is_symlink() or not pr_draft.parent.is_dir()):
                raise PermissionError("New private PR draft path required")
            with pr_draft.open("x", encoding="utf-8") as file:
                json.dump(record, file, sort_keys=True, indent=2)
            report["private_draft_saved"] = True
        return report
    if phase == "submit":
        reviews = read_local(base, token, "/v1/enterprise/reviews/integration",
                             opener=opener)
        revision = reviews.get("revision") if isinstance(reviews, dict) else None
        if type(revision) is not int or revision < 0:
            raise PermissionError("Exact live governance revision required")
        if not apply:
            return report
        if not journal.claim(str(uuid5(UUID(op["id"]), phase))):
            raise FileExistsError("PR proposal previously attempted")
        response = enterprise_call(base, token, method="POST", body={
            "command": "github_operation", "specification": op,
            "operation_key": op["id"], "base_revision": revision,
            "rationale": "DRAFT PR for verified commit " + proof["committed_sha"]
            + ", required CI: " + ", ".join(checks)
            + ". Independent QA reviewed; no merge or release.",
        }, opener=opener)
        if (not isinstance(response, dict)
                or response.get("command") != "github_operation"
                or response.get("operation_key") != op["id"]):
            raise PermissionError("AGO did not confirm immutable PR proposal")
        report["pr_proposal_id"] = str(UUID(str(response["id"])))
        report["approval_id"] = str(UUID(str(response["approval_id"])))
        return report
    pr_proposal = str(UUID(pr_proposal))
    reviews = read_local(base, token, "/v1/enterprise/reviews/integration",
                         opener=opener)
    checked_review(pr_proposal, op, reviews, me["id"])
    if phase == "execute":
        catalog = read_local(base, token, "/v1/platform/catalog", opener=opener)
        checked_applied(op, pr_proposal, catalog)
        status = read_local(
            base, token, "/v1/platform/github/projects/"
            + proof["project_id"] + "/status", opener=opener,
        )
        ci_gate(status, proof["committed_sha"], checks)
        if not isinstance(status.get("operations"), list) or any(
            isinstance(x, dict) and str(x.get("operation_id")) == op["id"]
            for x in status["operations"]
        ):
            raise PermissionError("Prior or uncertain GitHub PR dispatch")
    if not apply:
        return report
    if not journal.claim(str(uuid5(UUID(op["id"]), phase))):
        raise FileExistsError("PR stage previously attempted")
    if phase == "apply":
        response = post_local(
            base, token, "/v1/enterprise/reviews/integration/apply",
            {"proposal_id": pr_proposal}, opener=opener,
        )
        if (not isinstance(response, dict)
                or str(response.get("proposal_id")) != pr_proposal
                or not isinstance(response.get("result"), dict)
                or response["result"].get("id") != op["id"]
                or response["result"].get("kind") != "github_operation"):
            raise PermissionError("Exact independently approved PR apply not confirmed")
        report["governance_applied"] = True
        return report
    response = post_local(
        base, token, "/v1/platform/github/operations/" + op["id"] + "/execute",
        {}, opener=opener,
    )
    result = response.get("result") if isinstance(response, dict) else None
    number = result.get("number") if isinstance(result, dict) else None
    link = "https://github.com/" + proof["repository"] + "/pull/" + str(number)
    if (not isinstance(response, dict) or response.get("status") != "succeeded"
            or str(response.get("operation_id")) != op["id"]
            or type(number) is not int or number <= 0
            or result.get("head_sha") != proof["committed_sha"]
            or result.get("url") != link):
        raise PermissionError("Exact real GitHub draft PR receipt not confirmed")
    report.update({"github_pr_created": True, "draft_pr_number": number,
                   "draft_pr_url": link})
    return report


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--phase", choices=tuple(CONFIRMS), required=True)
    p.add_argument("--local-url", default="http://127.0.0.1:8000")
    for key in ("commit-draft", "export", "stage", "qa", "pr-draft"):
        p.add_argument("--" + key, type=Path, required=True)
    p.add_argument("--commit-proposal", required=True)
    p.add_argument("--pr-proposal", default="")
    p.add_argument("--operation-id", default="")
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--required-check", action="append", default=[])
    p.add_argument("--apply", action="store_true")
    p.add_argument("--confirm", default="")
    p.add_argument("--attempt-journal", type=Path,
                   default=Path.home() / ".ago" / "draft_pr_attempts")
    a = p.parse_args(argv)
    try:
        if a.apply and a.confirm != CONFIRMS[a.phase]:
            raise PermissionError("Exact phase consent required")
        base = local_url(a.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password, opener=LOCAL_OPENER)
        del password
        print(json.dumps(deliver(
            a.commit_draft, a.export, a.stage, a.qa, a.pr_draft,
            phase=a.phase, commit_proposal=a.commit_proposal, base=base,
            token=token, checks=a.required_check, operation_id=a.operation_id,
            title=a.title, body=a.body, pr_proposal=a.pr_proposal,
            apply=a.apply, confirm=a.confirm,
            journal=DurableAttemptJournal(a.attempt_journal) if a.apply
            and a.phase != "prepare" else None,
        ), sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "github_pr_created": False}))
        return 130
    except (ValueError, TypeError, KeyError, OSError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "github_pr_created": False, "release_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
