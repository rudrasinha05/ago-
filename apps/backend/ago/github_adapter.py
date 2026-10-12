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
        head = request("GET", root + "/git/ref/heads/develop")["object"]["sha"]
        if head != payload["expected_sha"]:
            raise PermissionError("Reviewed release head changed")
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


def validate_operation(value: dict) -> None:
    schemas = {
        "create_repository": set(),
        "link_repository": {"repository_id", "private"},
        "initialize_develop": {"expected_sha"},
        "create_issue": {"title", "body"},
        "update_issue": {"number", "title", "body", "state"},
        "commit_files": {"expected_sha", "message", "files"},
        "create_pull_request": {"expected_sha", "title", "body"},
    }
    op, p = value["operation"], value["payload"]
    if op not in schemas or not isinstance(p, dict) or set(p) != schemas[op]:
        raise ValueError("Exact supported GitHub operation fields required")
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
            ):
                raise ValueError("Safe unique bounded repository path required")
            seen.add(path)
        if sum(len(x["content"].encode()) for x in p["files"]) > 50000:
            raise ValueError("Reviewed change exceeds request budget")
