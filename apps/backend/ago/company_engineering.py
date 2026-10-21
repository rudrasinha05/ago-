"""Pure, untrusted model-to-code review gate: no execution, file writes or network.

A passed candidate proves ONLY that a small Python source/test pair parses.
Human review, actual tests, independent QA, GitHub review and release remain
distinct gates. Never treat this as a code execution sandbox.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re

from ago.github_adapter import validate_operation

_SAFE_SOURCE = re.compile(r"(?:src/[A-Za-z0-9_./-]+\.py|tests/test_[A-Za-z0-9_./-]+\.py|docs/[A-Za-z0-9_./-]+\.md)")
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?i:sk-(?:proj-)?[a-z0-9_-]{16,})|"
    r"(?i:gh[opusr]_[a-z0-9]{20,})"
)


def reviewed_candidate(raw: str) -> dict:
    """Return an exact-file, syntax-checked candidate; never execute it."""
    if not isinstance(raw, str) or not 1 <= len(raw.encode("utf-8")) <= 12000:
        raise ValueError("AI engineering response outside allowed size")
    try:
        document = json.loads(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("AI engineering response is not one JSON document") from exc
    if not isinstance(document, dict) or set(document) != {"files", "acceptance_checks"}:
        raise ValueError("Exact engineering candidate format required")
    files = document["files"]
    checks = document["acceptance_checks"]
    if (
        not isinstance(files, list) or not 2 <= len(files) <= 6
        or not isinstance(checks, list) or not 1 <= len(checks) <= 5
        or any(not isinstance(c, str) or not 1 <= len(c.strip()) <= 180 for c in checks)
    ):
        raise ValueError("Source and acceptance test plan required")
    if sum(len(x["content"].encode("utf-8")) for x in files
           if isinstance(x, dict) and isinstance(x.get("content"), str)) > 10000:
        raise ValueError("AI candidate exceeds bounded code budget")
    # Reuse the already reviewed GitHub exact-file/path validator. The dummy
    # parent SHA is intentionally NOT a real commit, credential or authority.
    validate_operation({
        "operation": "commit_files",
        "payload": {
            "expected_sha": "0" * 40,
            "message": "Uncommitted AGO engineering proposal",
            "files": files,
        },
    })
    if not all(_SAFE_SOURCE.fullmatch(item["path"]) for item in files):
        raise ValueError("Only small src/*.py, tests/test_*.py and docs/*.md candidates allowed")
    if not any(x["path"].startswith("src/") for x in files):
        raise ValueError("Python source file required")
    if not any(x["path"].startswith("tests/test_") for x in files):
        raise ValueError("Independent acceptance test source required")
    evidence = []
    for item in files:
        path, content = item["path"], item["content"]
        if _SECRET.search(content):
            raise ValueError("Potential secret material in AI candidate")
        if path.endswith(".py"):
            try:
                ast.parse(content, filename=path)
            except (SyntaxError, ValueError, TypeError) as exc:
                raise ValueError("Python source syntax failed in AI candidate") from exc
        evidence.append({
            "path": path,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
            "bytes": len(content.encode("utf-8")),
            "python_syntax_checked": path.endswith(".py"),
        })
    canonical = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return {
        "kind": "ago_unexecuted_engineering_candidate",
        "candidate_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": files,
        "file_evidence": evidence,
        "acceptance_checks": [c.strip() for c in checks],
        "source_parse_passed": True,
        "tests_executed": False,
        "github_committed": False,
        "qa_approved": False,
        "publishable": False,
        "next_gate": "Founder source review, isolated test execution, QA and reviewed GitHub operation",
    }


def verify_persisted_candidate(value: dict) -> dict:
    """Reject any post-inference tampering before the founder stages files."""
    if not isinstance(value, dict):
        raise ValueError("Stored engineering candidate required")
    expected = reviewed_candidate(json.dumps({
        "files": value.get("files"),
        "acceptance_checks": value.get("acceptance_checks"),
    }))
    # Evidence and digest must still describe precisely these source bytes.
    if (
        value.get("kind") != expected["kind"]
        or value.get("candidate_sha256") != expected["candidate_sha256"]
        or value.get("file_evidence") != expected["file_evidence"]
        or value.get("source_parse_passed") is not True
        or value.get("tests_executed") is not False
        or value.get("github_committed") is not False
        or value.get("qa_approved") is not False
        or value.get("publishable") is not False
    ):
        raise PermissionError("Engineering candidate changed after review")
    return expected


def stage_candidate(value: dict, destination) -> dict:
    """Write a *new*, explicit local review directory, never modify Git history."""
    from pathlib import Path

    candidate = verify_persisted_candidate(value)
    root = Path(destination)
    if root.exists() or root.is_symlink():
        raise FileExistsError("Review destination already exists; never overwrite")
    root.mkdir(parents=True, exist_ok=False)
    for item in candidate["files"]:
        target = root.joinpath(*item["path"].split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="") as handle:
            handle.write(item["content"])
    manifest = {
        "candidate_sha256": candidate["candidate_sha256"],
        "file_evidence": candidate["file_evidence"],
        "acceptance_checks": candidate["acceptance_checks"],
        "python_source_parsed": True,
        "tests_executed": False,
        "git_committed": False,
        "human_review_required": True,
    }
    with (root / "AGO_REVIEW_MANIFEST.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
    return manifest


def draft_github_commit_operation(
    value: dict, *, project_id: str, operation_id: str, expected_sha: str, message: str,
) -> dict:
    """Exact unsubmitted Section34 operation; never invokes GitHub or grants RBAC."""
    from uuid import UUID

    UUID(project_id)
    UUID(operation_id)
    candidate = verify_persisted_candidate(value)
    operation = {
        "id": operation_id,
        "project_id": project_id,
        "operation": "commit_files",
        "payload": {
            "expected_sha": expected_sha,
            "message": message,
            "files": candidate["files"],
        },
    }
    validate_operation(operation)
    return operation
