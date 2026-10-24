"""Explicit GitHub REST adapter: fixed host, bounded responses, no redirects or retries."""

from __future__ import annotations

import json
import os
import re
import http.client
from urllib.parse import quote

OWNER = "rudrasinha05"


def repository_name(value: str) -> str:
    if (
        not isinstance(value, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", value)
        or value.endswith(".git")
    ):
        raise ValueError("Simple GitHub repository name required")
    return value


def request(method: str, path: str, payload: dict | None = None) -> dict | list:
    token = os.getenv("AGO_GITHUB_TOKEN", "")
    if os.getenv("AGO_GITHUB_ENABLED") != "true" or not token:
        raise PermissionError(
            "Configure the owner-authorized GitHub credential and enable the connector"
        )
    if (
        method not in ("GET", "POST", "PATCH", "PUT")
        or not path.startswith(("/repos/" + OWNER + "/", "/user"))
        or ".." in path
        or "\\" in path
    ):
        raise ValueError("Fixed owner GitHub endpoint required")
    conn = http.client.HTTPSConnection("api.github.com", timeout=10)
    body = json.dumps(payload).encode() if payload is not None else None
    try:
        conn.request(
            method,
            path,
            body=body,
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "AGO-governed-project-service",
            },
        )
        response = conn.getresponse()
        data = response.read(2_000_001)
        if len(data) > 2_000_000:
            raise ValueError("GitHub response exceeds connector limit")
        if not 200 <= response.status < 300:
            raise ValueError(
                "GitHub request failed with status "
                + str(response.status)
                + "; inspect operation before retry"
            )
        return json.loads(data) if data else {}
    finally:
        conn.close()


def execute(project: dict, operation: dict, marker: str) -> dict:
    """All inputs already independently reviewed. This function never creates authority."""
    repo = repository_name(project["repository"])
    root = "/repos/" + OWNER + "/" + repo
    name = operation["operation"]
    payload = operation["payload"]
    if name == "create_repository":
        identity = request("GET", "/user")
        if identity["login"].lower() != OWNER:
            raise PermissionError("Repository ownership must remain with the CEO")
        result = request(
            "POST",
            "/user/repos",
            {
                "name": repo,
                "private": True,
                "auto_init": True,
                "description": "AGO project " + project["id"] + " " + marker,
            },
        )
        return {
            "repository_id": result["id"],
            "url": result["html_url"],
            "private": result["private"],
        }
    current = request("GET", root)
    if current["owner"]["login"].lower() != OWNER or current.get("archived"):
        raise PermissionError("Active CEO-owned repository required")
    if name == "link_repository":
        if current["id"] != payload["repository_id"] or current["private"] != payload["private"]:
            raise PermissionError("Existing repository identity or visibility changed since review")
        return {
            "repository_id": current["id"],
            "url": current["html_url"],
            "private": current["private"],
        }
    if current["id"] != project.get("repository_id") or current["private"] != project.get(
        "private"
    ):
        raise PermissionError("Repository must match the approved remote identity and visibility")
    if name == "create_issue":
        result = request(
            "POST",
            root + "/issues",
            {"title": payload["title"], "body": payload["body"] + "\n\n<!-- " + marker + " -->"},
        )
        return {"number": result["number"], "url": result["html_url"]}
    if name == "update_issue":
        result = request(
            "PATCH",
            root + "/issues/" + str(payload["number"]),
            {
                "title": payload["title"],
                "body": payload["body"] + "\n\n<!-- " + marker + " -->",
                "state": payload["state"],
            },
        )
        return {"number": result["number"], "url": result["html_url"]}
    if name == "initialize_develop":
        ref = request("GET", root + "/git/ref/heads/" + quote(current["default_branch"], safe=""))
        if ref["object"]["sha"] != payload["expected_sha"]:
            raise PermissionError("Default branch changed since approval")
        result = request(
            "POST",
            root + "/git/refs",
            {"ref": "refs/heads/develop", "sha": payload["expected_sha"]},
        )
        return {"sha": result["object"]["sha"]}
    if name == "commit_files":
        parent = request("GET", root + "/git/ref/heads/develop")["object"]["sha"]
        if parent != payload["expected_sha"]:
            raise PermissionError("Develop changed since code review")
        tree = request("GET", root + "/git/commits/" + parent)["tree"]["sha"]
        entries = [
            {"path": x["path"], "mode": "100644", "type": "blob", "content": x["content"]}
            for x in payload["files"]
        ]
        created = request("POST", root + "/git/trees", {"base_tree": tree, "tree": entries})
        commit = request(
            "POST",
            root + "/git/commits",
            {
                "message": payload["message"] + "\n\n" + marker,
                "tree": created["sha"],
                "parents": [parent],
            },
        )
        # Non-force update refuses concurrent divergent commits.
        request("PATCH", root + "/git/refs/heads/develop", {"sha": commit["sha"], "force": False})
        return {"sha": commit["sha"], "tree": created["sha"]}
    if name == "create_pull_request":
        if not current["private"] or project.get("private") is not True:
            raise PermissionError("Draft PR must target the bound private repository")
        head = request("GET", root + "/git/ref/heads/develop")["object"]["sha"]
        if head != payload["expected_sha"]:
            raise PermissionError("Reviewed release head changed")
        ci = inspect_required_ci(
            project, expected_sha=head,
            required_checks=tuple(payload["required_checks"]),
        )
        if ci["ci_verified"] is not True:
            raise PermissionError("All independently reviewed required CI checks must pass")
        result = request(
            "POST",
            root + "/pulls",
            {
                "title": payload["title"],
                "body": payload["body"] + "\n\n<!-- " + marker + " -->",
                "head": "develop",
                "base": "main",
                "draft": True,
            },
        )
        return {"number": result["number"], "url": result["html_url"], "head_sha": head}
    raise ValueError("Unsupported GitHub operation")



def inspect_required_ci(project: dict, *, expected_sha: str,
                        required_checks: tuple[str, ...]) -> dict:
    """Observe exact develop-HEAD CI without changing GitHub or granting release.

    A single green check does not establish a release. The project owner must
    supply every required named check; missing, duplicate, failing, pending or
    truncated provider evidence always blocks any positive verdict.
    """
    if not isinstance(expected_sha, str):
        raise TypeError("Exact reviewed commit SHA must be text")
    if not re.fullmatch("[a-f0-9]{40}", expected_sha):
        raise ValueError("Exact reviewed commit SHA required")
    if not isinstance(required_checks, tuple):
        raise TypeError("Required CI check names must be a tuple")
    if (not 1 <= len(required_checks) <= 24
            or any(not isinstance(x, str) or not 1 <= len(x) <= 120
                   for x in required_checks)
            or len(set(required_checks)) != len(required_checks)):
        raise ValueError("Explicit unique required CI checks are mandatory")
    name = repository_name(project["repository"])
    root = "/repos/" + OWNER + "/" + name
    remote = request("GET", root)
    if (remote.get("owner", {}).get("login", "").lower() != OWNER
            or remote.get("archived")
            or remote.get("id") != project.get("repository_id")
            or remote.get("private") != project.get("private")):
        raise PermissionError("GitHub project identity changed since approval")
    head = request("GET", root + "/git/ref/heads/develop")["object"]["sha"]
    if not isinstance(head, str) or not re.fullmatch("[a-f0-9]{40}", head):
        raise ValueError("GitHub develop reference is invalid")
    if head != expected_sha:
        raise PermissionError("Reviewed commit is no longer develop HEAD")
    checks = request("GET", root + "/commits/" + expected_sha + "/check-runs?per_page=100")
    statuses = request("GET", root + "/commits/" + expected_sha + "/status")
    if not isinstance(checks, dict) or not isinstance(statuses, dict):
        raise TypeError("GitHub CI response must contain objects")
    if (not isinstance(checks.get("check_runs"), list)
            or not isinstance(statuses.get("statuses"), list)):
        raise TypeError("GitHub CI evidence must contain lists")
    runs = checks["check_runs"]
    if checks.get("total_count", len(runs)) > len(runs):
        raise PermissionError("CI checks were truncated; cannot certify readiness")
    by_name = {check: [] for check in required_checks}
    for run in runs:
        name = run.get("name")
        if name in by_name:
            by_name[name].append(run.get("status") == "completed"
                                 and run.get("conclusion") == "success")
    for entry in statuses["statuses"]:
        name = entry.get("context")
        if name in by_name:
            by_name[name].append(entry.get("state") == "success")
    missing = [name for name, values in by_name.items() if not values]
    blocked = [name for name, values in by_name.items()
               if values and (len(values) > 1 or not all(values))]
    verified = not missing and not blocked
    return {"commit_sha": expected_sha, "develop_head": head,
            "required_checks": list(required_checks),
            "missing_checks": missing, "blocked_or_ambiguous_checks": blocked,
            "ci_verified": verified, "merge_authorized": False,
            "release_authorized": False,
            "status": "required_ci_passed" if verified else "required_ci_incomplete"}


def validate_operation(value: dict) -> None:
    schemas = {
        "create_repository": set(),
        "link_repository": {"repository_id", "private"},
        "initialize_develop": {"expected_sha"},
        "create_issue": {"title", "body"},
        "update_issue": {"number", "title", "body", "state"},
        "commit_files": {"expected_sha", "message", "files"},
        "create_pull_request": {"expected_sha", "title", "body", "required_checks"},
    }
    op, p = value["operation"], value["payload"]
    if op not in schemas or not isinstance(p, dict) or set(p) != schemas[op]:
        raise ValueError("Exact supported GitHub operation fields required")
    if op == "create_pull_request":
        checks = p["required_checks"]
        if (not isinstance(checks, list) or not 1 <= len(checks) <= 24
                or any(not isinstance(x, str) or not 1 <= len(x) <= 120 for x in checks)
                or len(set(checks)) != len(checks)):
            raise ValueError("Explicit unique required CI names are mandatory for draft PR")
    if op == "link_repository" and (
        type(p["repository_id"]) is not int
        or p["repository_id"] <= 0
        or type(p["private"]) is not bool
    ):
        raise ValueError("Reviewed existing repository ID and visibility required")
    if "expected_sha" in p and (
        not isinstance(p["expected_sha"], str)
        or not re.fullmatch("[a-f0-9]{40}", p["expected_sha"])
    ):
        raise ValueError("Reviewed exact commit SHA required")
    for k in ("title", "body", "message"):
        if k in p and (
            not isinstance(p[k], str) or not 1 <= len(p[k]) <= (12000 if k == "body" else 300)
        ):
            raise ValueError("Bounded title, content and rationale required")
    if "number" in p and (
        type(p["number"]) is not int or p["number"] <= 0 or p["state"] not in ("open", "closed")
    ):
        raise ValueError("Positive issue number and explicit state required")
    if "files" in p:
        # The destination is private, but even a private Git repository is
        # not a credential vault. Never export known token/key material.
        private_file = re.compile(
            r"(?i)(?:^|/)(?:\\.env(?:\\.[^/]*)?|id_(?:rsa|ed25519)|"
            r"[^/]*(?:credentials?|private[_-]?key|secrets?)[^/]*\\.(?:json|ya?ml|ini|txt)|"
            r"[^/]*\\.(?:pem|p12|pfx|key|dump|backup|pgdump))$"
        )
        private_content = re.compile(
            r"-----BEGIN (?:RSA |EC |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"
            r"|\\bgithub_pat_[A-Za-z0-9_]{20,}"
            r"|\\bgh[pousr]_[A-Za-z0-9]{30,}"
            r"|\\bAKIA[A-Z0-9]{16}\\b"
            r"|\\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}"
        )
        if not isinstance(p["files"], list) or not 1 <= len(p["files"]) <= 20:
            raise ValueError("One to twenty reviewed files required")
        seen = set()
        for file in p["files"]:
            if (
                not isinstance(file, dict)
                or set(file) != {"path", "content"}
                or not isinstance(file["path"], str)
                or not isinstance(file["content"], str)
            ):
                raise ValueError("Exact text file required")
            path = file["path"]
            if (
                not re.fullmatch(r"[A-Za-z0-9_.\-/]{1,250}", path)
                or path.startswith(("/", ".git/", ".env"))
                or any(x in ("", ".", "..") for x in path.split("/"))
                or path in seen
                or len(file["content"].encode()) > 40000
                or private_file.search(path) is not None
                or private_content.search(file["content"]) is not None
            ):
                raise ValueError("Safe unique bounded repository path required")
            seen.add(path)
        if sum(len(x["content"].encode()) for x in p["files"]) > 50000:
            raise ValueError("Reviewed change exceeds request budget")
