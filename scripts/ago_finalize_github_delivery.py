"""Founder-controlled apply/execute for previously human-approved AGO GitHub work.

Reuses the existing server's independent reviewer, scope, GitHub identity,
non-force HEAD CAS and durable dispatch state. This client NEVER self-approves.
Each mutating step uses a separate one-shot local journal and explicit consent.
"""
from __future__ import annotations

import argparse
import getpass
import json
import re
import sys
from pathlib import Path
from urllib.request import Request
from uuid import UUID, uuid5

from ago_human_qa_handoff import LOCAL_OPENER
from ago_submit_github_proposal import inspect_verified_draft
from local_approved_agent_batch import DurableAttemptJournal, founder_login, local_url

APPLY_CONFIRM = "APPLY_INDEPENDENTLY_APPROVED_GITHUB_OPERATION"
EXECUTE_CONFIRM = "EXECUTE_APPROVED_GITHUB_COMMIT"
MAX_READ = 100000


def read_local(base: str, token: str, endpoint: str, *, opener=LOCAL_OPENER):
    """Fixed allowlist prevents arbitrary SSRF, redirects and proxy fallback."""
    allow = (
        endpoint in ("/v1/console/me", "/v1/enterprise/reviews/integration",
                     "/v1/platform/catalog")
        or re.fullmatch(
            r"/v1/platform/github/projects/[a-f0-9-]{36}/status", endpoint
        ) is not None
    )
    if not allow or not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise PermissionError("Exact signed localhost read required")
    req = Request(
        local_url(base) + endpoint, method="GET",
        headers={"Authorization": "Bearer " + token, "Accept": "application/json"},
    )
    with opener(req, timeout=20) as response:
        raw = response.read(MAX_READ + 1)
    if len(raw) > MAX_READ:
        raise ValueError("AGO read response exceeds limit")
    return json.loads(raw)


def post_local(base: str, token: str, endpoint: str, payload: dict, *,
               opener=LOCAL_OPENER):
    """The only mutating calls are AGO apply and AGO authorized dispatch."""
    allow = (
        endpoint == "/v1/enterprise/reviews/integration/apply"
        or re.fullmatch(
            r"/v1/platform/github/operations/[a-f0-9-]{36}/execute", endpoint
        ) is not None
    )
    if not allow or not isinstance(token, str) or not 1 <= len(token) <= 4096:
        raise PermissionError("Only reviewed AGO apply/execute supported")
    data = json.dumps(payload).encode("utf-8")
    if len(data) > 2048:
        raise ValueError("Mutating request exceeds strict budget")
    req = Request(
        local_url(base) + endpoint, data=data, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Accept": "application/json", "Content-Type": "application/json"},
    )
    with opener(req, timeout=30) as response:
        raw = response.read(MAX_READ + 1)
    if len(raw) > MAX_READ:
        raise ValueError("AGO delivery receipt exceeds limit")
    return json.loads(raw)


def checked_review(proposal_id: str, operation: dict, reviews: dict,
                   founder_id: str) -> dict:
    """The exact original human-approved proposal, never another project."""
    UUID(proposal_id)
    if not isinstance(reviews, dict) or not isinstance(reviews.get("proposals"), list):
        raise TypeError("Live enterprise review inventory required")
    candidates = [
        x for x in reviews["proposals"]
        if isinstance(x, dict) and str(x.get("id")) == proposal_id
    ]
    if len(candidates) != 1:
        raise PermissionError("Exact same-tenant governance proposal not visible")
    p = candidates[0]
    if (p.get("domain") != "integration"
            or p.get("command") != "github_operation"
            or p.get("status") != "approved"
            or str(p.get("actor_id")) != founder_id
            or str(p.get("approval_id")) == founder_id
            or p.get("operation_key") != operation["id"]
            or p.get("specification") != operation):
        raise PermissionError("Independent human-approved exact operation is required")
    return p


def checked_applied(operation: dict, proposal_id: str, catalog: dict) -> dict:
    """AGO server must have applied the original approved operation itself."""
    if (not isinstance(catalog, dict)
            or not isinstance(catalog.get("github_operations"), list)):
        raise TypeError("Live AGO integration catalog required")
    rows = [
        x for x in catalog["github_operations"]
        if isinstance(x, dict) and str(x.get("id")) == operation["id"]
    ]
    if len(rows) != 1:
        raise PermissionError("Operation not applied through enterprise governance")
    row = rows[0]
    if (row.get("kind") != "github_operation"
            or row.get("payload") != operation
            or str(row.get("proposal_id")) != proposal_id):
        raise PermissionError("Applied operation payload or approval identity changed")
    return row


def verified_delivery(
    draft: Path, source: Path, stage: Path, qa: Path,
    *, base: str, token: str, proposal_id: str, action: str,
    apply=False, confirm="", journal: DurableAttemptJournal | None = None,
    opener=LOCAL_OPENER,
) -> dict:
    if action not in ("apply", "execute"):
        raise ValueError("Explicit apply or execute phase required")
    verified = inspect_verified_draft(
        draft, source, stage, qa, base=base, token=token, opener=opener,
    )
    operation = verified["operation"]
    me = read_local(base, token, "/v1/console/me", opener=opener)
    if (not isinstance(me, dict) or "founder" not in me.get("roles", [])
            or not isinstance(me.get("id"), str)):
        raise PermissionError("Authenticated original Founder session required")
    reviews = read_local(base, token, "/v1/enterprise/reviews/integration",
                         opener=opener)
    checked_review(proposal_id, operation, reviews, me["id"])
    expected = operation["payload"]["expected_sha"]
    proof = verified["qa"]
    out = {
        "kind": "ago_reviewed_github_delivery",
        "action": action,
        "mode": "preview" if not apply else "submitted_to_ago",
        "proposal_id": proposal_id,
        "operation_id": operation["id"],
        "github_project_id": operation["project_id"],
        "candidate_sha256": proof["candidate_sha256"],
        "founder_reviewed_develop_sha": expected,
        "human_qa_reviewer_id": proof["qa_reviewer_id"],
        "independent_enterprise_approval": "approved",
        "remote_write_attempted": False, "github_committed": False,
        "release_ready": False,
    }
    if action == "execute":
        catalog = read_local(base, token, "/v1/platform/catalog", opener=opener)
        checked_applied(operation, proposal_id, catalog)
        live = read_local(
            base, token,
            "/v1/platform/github/projects/" + operation["project_id"] + "/status",
            opener=opener,
        )
        if (not isinstance(live, dict)
                or str(live.get("project_id")) != operation["project_id"]
                or live.get("repository_private") is not True
                or live.get("develop_sha") != expected
                or not isinstance(live.get("operations"), list)
                or any(str(x.get("operation_id")) == operation["id"]
                       for x in live["operations"] if isinstance(x, dict))):
            raise PermissionError(
                "Expected develop HEAD or operation dispatch state differs; reconcile"
            )
        out["remote_develop_head_verified"] = True
    else:
        out["remote_develop_head_verified"] = False
    if not apply:
        return out
    if journal is None or confirm != (
        APPLY_CONFIRM if action == "apply" else EXECUTE_CONFIRM
    ):
        raise PermissionError("Explicit phase-specific authorization required")
    # Different namespaces: a completed apply can never pre-consume execute.
    claim_id = str(uuid5(UUID(operation["id"]), action))
    if not journal.claim(claim_id):
        raise FileExistsError("Prior AGO write may have succeeded; inspect remote state")
    if action == "apply":
        response = post_local(
            base, token, "/v1/enterprise/reviews/integration/apply",
            {"proposal_id": proposal_id}, opener=opener,
        )
        if (not isinstance(response, dict)
                or str(response.get("proposal_id")) != proposal_id
                or not isinstance(response.get("result"), dict)
                or response["result"].get("id") != operation["id"]
                or response["result"].get("kind") != "github_operation"):
            raise PermissionError("AGO did not confirm the exact approved apply receipt")
        out["governance_applied"] = True
        return out
    response = post_local(
        base, token,
        "/v1/platform/github/operations/" + operation["id"] + "/execute",
        {}, opener=opener,
    )
    if (not isinstance(response, dict)
            or response.get("status") != "succeeded"
            or str(response.get("operation_id")) != operation["id"]
            or not isinstance(response.get("result"), dict)
            or not re.fullmatch(r"[0-9a-f]{40}", response["result"].get("sha", ""))):
        raise PermissionError("AGO did not confirm a real committed GitHub SHA")
    out["remote_write_attempted"] = True
    out["github_committed"] = True
    out["committed_sha"] = response["result"]["sha"]
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", required=True, choices=("apply", "execute"))
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    for name in ("draft", "export", "staged-directory", "qa-packet"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--attempt-journal", type=Path,
                        default=Path.home() / ".ago" / "github_delivery_attempts")
    args = parser.parse_args(argv)
    try:
        if args.apply and args.confirm != (
            APPLY_CONFIRM if args.action == "apply" else EXECUTE_CONFIRM
        ):
            raise PermissionError("Exact phase-specific Founder confirmation required")
        base = local_url(args.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Original Founder email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password, opener=LOCAL_OPENER)
        del password
        result = verified_delivery(
            args.draft, args.export, args.staged_directory, args.qa_packet,
            base=base, token=token, proposal_id=args.proposal_id,
            action=args.action, apply=args.apply, confirm=args.confirm,
            journal=DurableAttemptJournal(args.attempt_journal) if args.apply else None,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "github_committed": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "github_committed": False, "release_ready": False}),
              file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
