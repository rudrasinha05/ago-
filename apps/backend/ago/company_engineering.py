"""Untrusted model-to-code review gate.

A passed candidate proves ONLY that a small Python source/test pair parses.
``run_candidate_tests`` is the one place that executes a candidate: its tests
run inside an offline, read-only, unprivileged Docker container, never in the
host Python. Independent QA, GitHub review and release remain distinct gates.
"""
from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

from ago.github_adapter import validate_operation

class EngineeringCandidateInvalid(ValueError):
    """The AI developer's code proposal failed AGO's static review twice."""

    failure_code = "engineering_candidate_invalid"


_SAFE_SOURCE = re.compile(r"(?:src/[A-Za-z0-9_./-]+\.py|tests/test_[A-Za-z0-9_./-]+\.py|docs/[A-Za-z0-9_./-]+\.md)")
_SECRET = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    r"(?i:sk-(?:proj-)?[a-z0-9_-]{16,})|"
    r"(?i:gh[opusr]_[a-z0-9]{20,})"
)


# Shape of one candidate, given to a local provider that can constrain its
# answer. It only shapes the model output; reviewed_candidate stays the gate.
ENGINEERING_CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "files": {
            "type": "array", "minItems": 2, "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"], "additionalProperties": False,
            },
        },
        "acceptance_checks": {
            "type": "array", "minItems": 1, "maxItems": 5, "items": {"type": "string"},
        },
    },
    "required": ["files", "acceptance_checks"], "additionalProperties": False,
}


def _without_code_fence(raw: str) -> str:
    """Remove ONE Markdown code fence that wraps the whole answer, nothing else.

    Small local models wrap valid JSON in ```json ... ``` even when told not to.
    Only an answer that both starts and ends with a fence is unwrapped; prose
    before or after the fence is left in place and still fails the JSON check.
    """
    text = raw.strip()
    if not (text.startswith("```") and text.endswith("```")) or len(text) < 6:
        return raw
    first_line, separator, body = text[3:-3].partition("\n")
    if not separator or first_line.strip().lower() not in ("", "json"):
        return raw
    return body.strip()


def reviewed_candidate(raw: str) -> dict:
    """Return an exact-file, syntax-checked candidate; never execute it."""
    if not isinstance(raw, str) or not 1 <= len(raw.encode("utf-8")) <= 12000:
        raise ValueError("AI engineering response outside allowed size")
    try:
        document = json.loads(_without_code_fence(raw))
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
    # The persisted candidate stores trimmed checks. Hash that exact canonical
    # representation, not the untrusted pre-normalization model response;
    # otherwise harmless whitespace makes verify_persisted_candidate reject a
    # valid candidate before staging or QA can begin.
    normalized_checks = [check.strip() for check in checks]
    canonical = json.dumps(
        {"files": files, "acceptance_checks": normalized_checks},
        sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    )
    return {
        "kind": "ago_unexecuted_engineering_candidate",
        "candidate_sha256": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        "files": files,
        "file_evidence": evidence,
        "acceptance_checks": normalized_checks,
        "source_parse_passed": True,
        "tests_executed": False,
        "github_committed": False,
        "qa_approved": False,
        "publishable": False,
        "next_gate": "Founder source review, isolated test execution, QA and reviewed GitHub operation",
    }


def assert_discoverable_unittest(value: dict) -> dict:
    """Fail closed unless EVERY generated test file is unittest-discoverable.

    This static preflight neither imports candidate modules nor runs their tests.
    The separately authorized offline Docker gate remains the only test evidence.
    """
    source_modules = {
        item["path"][:-3].replace("/", ".")
        for item in value["files"]
        if item["path"].startswith("src/") and item["path"].endswith(".py")
    }
    tests = [
        item for item in value["files"]
        if item["path"].startswith("tests/test_")
    ]
    if not tests:
        raise ValueError("AI code must include discoverable unittest.TestCase test_* methods")
    for item in tests:
        # unittest.discover('tests', pattern='test_*.py') does not descend into
        # generated nested directories without package initialization files.
        if item["path"].count("/") != 1:
            raise ValueError("AI unittest path must be a flat tests/test_*.py file")
        tree = ast.parse(item["content"], filename=item["path"])
        imports_unittest = any(
            isinstance(node, ast.Import)
            and any(alias.name == "unittest" and alias.asname in (None, "unittest")
                    for alias in node.names)
            for node in tree.body
        )
        has_test_case = any(
            isinstance(cls, ast.ClassDef)
            and any(
                isinstance(base, ast.Attribute)
                and base.attr == "TestCase"
                and isinstance(base.value, ast.Name)
                and base.value.id == "unittest"
                for base in cls.bases
            )
            and any(
                isinstance(method, ast.FunctionDef)
                and method.name.startswith("test_")
                for method in cls.body
            )
            for cls in tree.body
        )
        if not imports_unittest or not has_test_case:
            raise ValueError(
                "AI code must include discoverable unittest.TestCase test_* methods "
                "in every test file"
            )
        # Test files that only assert True are discoverable but need not
        # exercise the proposed implementation. Require a static import link,
        # without pretending to prove semantic coverage or passing tests.
        links_source = any(
            (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module in source_modules
            ) or (
                isinstance(node, ast.Import)
                and any(alias.name in source_modules for alias in node.names)
            )
            for node in ast.walk(tree)
        )
        if not links_source:
            raise ValueError("AI acceptance tests must import a generated src module")
    return value


def assert_documented(value: dict) -> dict:
    """The implementation deliverable includes technical documentation.

    QA's stage acceptance is "code, tests and technical documentation"; a
    candidate without a docs/*.md file could never pass it.
    """
    docs = [f for f in value.get("files") or []
            if isinstance(f, dict) and str(f.get("path", "")).startswith("docs/")
            and len(str(f.get("content") or "").strip()) >= 20]
    if not docs:
        raise ValueError("A docs/*.md file explaining the module is required")
    return value


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


# ---------------------------------------------------------------------------
# Isolated test execution of a persisted candidate (QA-002 / QA-003).
#
# The implementation stage's tests used to be "prepared" but never run, so AI
# QA and the Board failed every attempt with "tests are not executed". AGO now
# runs them itself, the same way the CI Docker smoke and the Founder's local
# script do: no network, read-only, non-root, bounded memory/CPU/processes,
# and only the reviewed files are mounted.
# ---------------------------------------------------------------------------
TEST_IMAGE = "python:3.11-slim"
TEST_TIMEOUT_SECONDS = 90
_CASES_MARKER = "AGO_UNITTEST_CASES="
_TEST_RUNNER = (
    "import sys,unittest;"
    "suite=unittest.defaultTestLoader.discover('tests',pattern='test_*.py');"
    "n=suite.countTestCases();print('AGO_UNITTEST_CASES='+str(n),flush=True);"
    "sys.exit(4) if n==0 else "
    "sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)"
)
_FAILURE_LABELS = (
    ("AssertionError", "assertion_failure"),
    ("ModuleNotFoundError", "missing_module"),
    ("ImportError", "import_error"),
    ("SyntaxError", "syntax_error"),
    ("NameError", "name_error"),
    ("AttributeError", "attribute_error"),
    ("TypeError", "type_error"),
    ("KeyError", "key_error"),
    ("ValueError", "value_error"),
)
_CONTROL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def isolated_test_command(root: Path, container_name: str) -> list[str]:
    """The exact docker invocation; the image must already be present (no pull)."""
    if not re.fullmatch(r"ago-test-[a-f0-9]{32}", container_name):
        raise ValueError("Random isolated container name required")
    return [
        "docker", "run", "--rm", "--pull=never",
        "--name", container_name, "--network", "none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--memory=256m", "--cpus=1",
        "--user=65534:65534", "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
        "--mount", "type=bind,src=" + str(root.resolve()) + ",dst=/work,readonly",
        "--workdir=/work", "--env=PYTHONPATH=/work",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        TEST_IMAGE, "python", "-c", _TEST_RUNNER,
    ]


def failure_summary(output: str, limit: int = 700) -> str:
    """The lines a developer needs to fix a failing test, bounded and inert.

    Keeps unittest's FAIL/ERROR headers, the final exception lines and the
    summary; drops everything else (and every control character). This is the
    project's own generated code and tests, stored only in the tenant record.
    """
    keep = []
    for line in _CONTROL.sub("", output).splitlines():
        text = line.rstrip()
        if not text:
            continue
        if (text.startswith(("FAIL:", "ERROR:", "Ran ", "FAILED", "OK"))
                or re.match(r"^[A-Za-z_.]*(Error|Exception)\b", text)
                or text.lstrip().startswith(("File \"/work/", "AssertionError"))):
            keep.append(text.replace("/work/", "")[:200])
    summary = "\n".join(dict.fromkeys(keep))
    return summary[-limit:] if len(summary) > limit else summary


def test_runner_available(*, runner=subprocess.run) -> bool:
    """Docker answers and the test image is already on this computer (no pull)."""
    try:
        probe = runner(["docker", "image", "inspect", TEST_IMAGE], capture_output=True,
                       text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def run_candidate_tests(value: dict, *, runner=subprocess.run,
                        timeout: int = TEST_TIMEOUT_SECONDS) -> dict:
    """Run a persisted candidate's unittest suite in an isolated container.

    Returns a receipt with ``status`` one of: ``passed``, ``failed``,
    ``timeout`` or ``runner_unavailable`` (Docker or the image is missing - a
    machine problem, not a defect of the code, and nothing was executed).
    """
    candidate = verify_persisted_candidate(value)
    base = {
        "kind": "ago_isolated_candidate_test_receipt_v1",
        "candidate_sha256": candidate["candidate_sha256"],
        "image": TEST_IMAGE, "network_disabled": True, "read_only_container": True,
        "unittest_cases": 0, "tests_executed": False, "tests_passed": False,
        "failure_category": "none", "failure_summary": "", "docker_exit_code": None,
    }
    if not test_runner_available(runner=runner):
        return {**base, "status": "runner_unavailable",
                "failure_summary": "Docker is not running or the " + TEST_IMAGE
                                   + " image is not present on this computer."}
    with tempfile.TemporaryDirectory(prefix="ago-test-") as temp:
        root = Path(temp) / "work"
        stage_candidate(candidate, root)
        # The container user (nobody) must be able to read the mounted files.
        for path in [Path(temp), *root.rglob("*"), root]:
            try:
                os.chmod(path, 0o755 if path.is_dir() else 0o644)
            except OSError:
                pass
        container = "ago-test-" + uuid4().hex
        try:
            result = runner(isolated_test_command(root, container), capture_output=True,
                            text=True, timeout=timeout, check=False)
        except subprocess.TimeoutExpired:
            try:
                runner(["docker", "rm", "-f", container], capture_output=True, text=True,
                       timeout=15, check=False)
            except (OSError, subprocess.SubprocessError):
                pass
            return {**base, "status": "timeout", "failure_category": "timeout",
                    "failure_summary": "The tests did not finish within "
                                       + str(timeout) + " seconds (possible endless loop)."}
        except (OSError, subprocess.SubprocessError):
            return {**base, "status": "runner_unavailable",
                    "failure_summary": "Docker could not start the test container."}
    output = str(result.stdout or "") + "\n" + str(result.stderr or "")
    seen = re.findall(r"(?:^|\n)" + _CASES_MARKER + r"(\d+)(?:\r?\n|$)", output)
    cases = int(seen[0]) if len(seen) == 1 else 0
    passed = result.returncode == 0 and cases >= 1
    category = "none" if passed else "tests_not_discovered" if not cases else next(
        (label for token, label in _FAILURE_LABELS if token in output), "unclassified_failure")
    return {
        **base,
        "status": "passed" if passed else "failed",
        "unittest_cases": cases, "tests_executed": cases >= 1, "tests_passed": passed,
        "failure_category": category,
        "failure_summary": "" if passed else (failure_summary(output) or category),
        "docker_exit_code": result.returncode,
        "output_sha256": hashlib.sha256(output.encode("utf-8")).hexdigest(),
    }


def receipt_text(receipt: dict) -> str:
    """One plain line for QA, the Board and the developer."""
    cases = int(receipt.get("unittest_cases") or 0)
    if receipt.get("status") == "passed":
        return ("AGO ISOLATED TEST RECEIPT: " + str(cases) + " unittest case(s) were EXECUTED by "
                "AGO in an offline, read-only Docker container and ALL PASSED.")
    return ("AGO ISOLATED TEST RECEIPT: tests FAILED ("
            + str(receipt.get("failure_category") or "failure") + ", " + str(cases)
            + " case(s) found). " + str(receipt.get("failure_summary") or ""))[:900]
