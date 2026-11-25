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
    return _review_candidate(raw, workspace=False)


def _review_candidate(raw: str, *, workspace: bool) -> dict:
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
    def supported(path):
        if workspace and re.fullmatch(r"(?:src|tests)/[A-Za-z0-9_./-]+\.(?:js|mjs|cjs)", path):
            return True
        return bool(_SAFE_SOURCE.fullmatch(path))

    if not all(supported(item["path"]) for item in files):
        raise ValueError("Only small src/*.py, tests/test_*.py and docs/*.md candidates allowed")
    if not any(x["path"].startswith("src/") for x in files):
        raise ValueError("Python source file required")
    if not any(x["path"].startswith("tests/test_") or (workspace and x["path"].startswith("tests/") and x["path"].endswith((".test.js", ".test.cjs", ".test.mjs"))) for x in files):
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
    # Live 2026-11-18: the developer copied the test's "from src.x import X"
    # line into src/x.py itself -> circular import, every test failed in Docker.
    for item in value["files"]:
        if not (item["path"].startswith("src/") and item["path"].endswith(".py")):
            continue
        own = item["path"][:-3].replace("/", ".")
        for node in ast.walk(ast.parse(item["content"], filename=item["path"])):
            named = ([node.module or ""] if isinstance(node, ast.ImportFrom)
                     else [a.name for a in node.names] if isinstance(node, ast.Import) else [])
            if any(name in (own, own.split(".", 1)[-1]) for name in named):
                raise ValueError(item["path"] + " imports itself; only the test file imports "
                                 "from " + own + " - remove that line from the source file")
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


def verify_persisted_candidate(value: dict, *, workspace: bool = False) -> dict:
    """Reject any post-inference tampering before the founder stages files."""
    if not isinstance(value, dict):
        raise ValueError("Stored engineering candidate required")
    expected = _review_candidate(json.dumps({
        "files": value.get("files"),
        "acceptance_checks": value.get("acceptance_checks"),
    }), workspace=workspace)
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


def stage_candidate(value: dict, destination, *, workspace: bool = False) -> dict:
    """Write a *new*, explicit local review directory, never modify Git history."""
    from pathlib import Path

    candidate = verify_persisted_candidate(value, workspace=workspace)
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
    value: dict, *, project_id: str, operation_id: str, expected_sha: str, message: str, workspace: bool = False,
) -> dict:
    """Exact unsubmitted Section34 operation; never invokes GitHub or grants RBAC."""
    from uuid import UUID

    UUID(project_id)
    UUID(operation_id)
    candidate = verify_persisted_candidate(value, workspace=workspace)
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


def test_runner_available(*, runner=subprocess.run, image=TEST_IMAGE) -> bool:
    """Docker answers and the test image is already on this computer (no pull)."""
    try:
        probe = runner(["docker", "image", "inspect", image], capture_output=True,
                       text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return False
    return probe.returncode == 0


def _write_files(files: list[dict], root: Path) -> None:
    """Write an exact, already validated file set into a new directory."""
    root.mkdir(parents=True, exist_ok=False)
    for item in files:
        target = root.joinpath(*item["path"].split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="") as handle:
            handle.write(item["content"])


def run_candidate_tests(value: dict, *, runner=subprocess.run,
                        timeout: int = TEST_TIMEOUT_SECONDS, workspace: bool = False,
                        with_files: list[dict] | None = None) -> dict:
    """Run a persisted candidate's unittest suite in an isolated container.

    ``with_files`` (PROJ-014): the complete integrated project INCLUDING this
    candidate. Then every earlier test runs together with the new ones
    (complete regression), so a module that breaks an older module fails.

    Returns a receipt with ``status`` one of: ``passed``, ``failed``,
    ``timeout`` or ``runner_unavailable`` (Docker or the image is missing - a
    machine problem, not a defect of the code, and nothing was executed).
    """
    candidate = verify_persisted_candidate(value, workspace=workspace)
    if with_files is not None:
        from ago.project_modules import check_project_files
        check_project_files(with_files)
        listed = {(f["path"], f["content"]) for f in with_files}
        if not all((f["path"], f["content"]) in listed for f in candidate["files"]):
            raise ValueError("The project file set must contain this candidate unchanged")
    node_files = [f["path"] for f in candidate["files"] if f["path"].endswith((".js", ".cjs", ".mjs"))]
    node_tests = [p for p in node_files if p.startswith("tests/")]
    image = "node:22-alpine" if node_files else TEST_IMAGE
    base = {
        "kind": "ago_isolated_candidate_test_receipt_v1",
        "candidate_sha256": candidate["candidate_sha256"],
        "image": image, "network_disabled": True, "read_only_container": True,
        "unittest_cases": 0, "tests_executed": False, "tests_passed": False,
        "failure_category": "none", "failure_summary": "", "docker_exit_code": None,
        "regression": with_files is not None,
        "files_tested": len(with_files) if with_files is not None else len(candidate["files"]),
    }
    if node_files and (not node_tests or any(f["path"].endswith(".py") for f in candidate["files"])):
        return {**base, "status": "unsupported_suite", "failure_summary":
                "Select a single runtime and include matching test files for this revision."}
    if not test_runner_available(runner=runner, image=image):
        return {**base, "status": "runner_unavailable",
                "failure_summary": "Docker is not running or the " + image
                                   + " image is not present on this computer."}
    with tempfile.TemporaryDirectory(prefix="ago-test-") as temp:
        root = Path(temp) / "work"
        if with_files is not None:
            _write_files(with_files, root)
        else:
            stage_candidate(candidate, root, workspace=workspace)
        # The container user (nobody) must be able to read the mounted files.
        for path in [Path(temp), *root.rglob("*"), root]:
            try:
                os.chmod(path, 0o755 if path.is_dir() else 0o644)
            except OSError:
                pass
        container = "ago-test-" + uuid4().hex
        try:
            command = isolated_test_command(root, container)
            if node_files:
                command = command[:-4] + [image, "node", "--test", "--test-reporter=tap", *node_tests]
            result = runner(command, capture_output=True,
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
    if node_files:
        seen = re.findall(r"^# tests (\d+)$", output, re.MULTILINE)
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


def project_test_evidence_text(candidate: dict, *, cases: int) -> str:
    """What a later stage (quality, release) may rely on: AGO's executed tests.

    Built only from a PASSED receipt and the stored candidate it tested, never
    from model text. It names the test cases and the checks they cover so the
    QA plan and its reviewer can cite real, executed tests.
    """
    files = [f for f in (candidate.get("files") or []) if isinstance(f, dict)]
    paths = [str(f.get("path")) for f in files]
    names = []
    for f in files:
        if str(f.get("path", "")).startswith("tests/"):
            names += re.findall(r"def (test_[A-Za-z0-9_]+)", str(f.get("content") or ""))
    checks = [str(c) for c in candidate.get("acceptance_checks") or []][:6]
    # Most important facts first: prompts may keep only the first 200 characters.
    return ("AGO TEST EVIDENCE: " + str(int(cases)) + " test(s) EXECUTED by AGO in offline "
            "Docker, ALL PASSED: " + (", ".join(names)[:400] or "see tests/")
            + ". Files: " + ", ".join(paths)[:300] + ". Acceptance checks: "
            + "; ".join(checks)[:400] + ". (Recorded by AGO, not written by a model.)")[:1200]


# One fixed, checkable shape per text-only later stage. The worker writes these
# labelled lines and AI QA checks the same labels, so a small model cannot fail
# the work for being "not detailed enough" (live 2026-11-21, quality stage).
STAGE_FORMATS = {
    # PROJ-014: the architect plans the modules; AGO reads the MODULES line into
    # the module plan the Founder approves before implementation starts.
    "architecture": ("ARCHITECTURE", "MODULES"),
    "quality": ("QA PLAN", "TEST CASES", "TEST REPORT", "ACCEPTANCE MAP", "RELEASE BLOCKERS"),
    "release": ("RELEASE PACKAGE", "PR TITLE", "PR DESCRIPTION", "RELEASE NOTES",
                "RECOMMENDATION"),
}
STAGE_FORMAT_HINTS = {
    "architecture": ("ARCHITECTURE: the main parts and how they connect; MODULES: M01 Name - "
                     "what it does; M02 Name - what it does; ... (small modules, each one "
                     "engineer task, built on a working prototype)"),
    "quality": ("TEST CASES: the test names in AGO TEST EVIDENCE; TEST REPORT: how many "
                "AGO executed and that all passed; ACCEPTANCE MAP: each check -> its test; "
                "RELEASE BLOCKERS: none, or each blocker"),
    "release": ("RELEASE PACKAGE: the files; RECOMMENDATION: release or hold for the "
                "owner, with one reason"),
}


def stage_format_rule(stage: str) -> str:
    """The worker's required labelled lines for this stage ('' if free form)."""
    labels = STAGE_FORMATS.get(stage)
    if not labels:
        return ""
    return ("FORMAT: start DELIVERABLE with one short line for each label (under 900 "
            "characters in total), in this order: " + "; ".join(label + ":" for label in labels) + " ("
            + STAGE_FORMAT_HINTS[stage] + ").")


def missing_stage_labels(stage: str, text: str) -> list[str]:
    """Labels of this stage's format that the deliverable does not contain."""
    upper = str(text or "").upper()
    return [label for label in STAGE_FORMATS.get(stage, ()) if label + ":" not in upper]


class RevisionConflict(ValueError):
    pass


def workspace_snapshot(row, draft):
    if not row:
        raise LookupError("Project stage task not found")
    result = row["run_result"] or {}
    if row["run_status"] != "completed" or not result.get("engineering_candidate"):
        raise LookupError("This task has no completed engineering candidate")
    original = verify_persisted_candidate(result["engineering_candidate"])
    current = verify_persisted_candidate(draft["candidate"], workspace=True) if draft else original
    return {
        "run_id": str(row["run_id"]),
        "revision": draft["revision"] if draft else 0,
        "original_sha256": original["candidate_sha256"],
        "candidate_sha256": current["candidate_sha256"],
        "files": current["files"],
        "acceptance_checks": current["acceptance_checks"],
    }


def edited_candidate(snapshot, changes):
    if not isinstance(changes, dict) or set(changes) != {"run_id", "expected_revision", "files"}:
        raise ValueError("run_id, expected_revision and files are required")
    revision = changes["expected_revision"]
    if type(revision) is not int or revision < 0:
        raise ValueError("Invalid workspace revision")
    if changes["run_id"] != snapshot["run_id"] or revision != snapshot["revision"]:
        raise RevisionConflict("Workspace changed. Reload before saving.")
    return _review_candidate(json.dumps({
        "files": changes["files"], "acceptance_checks": snapshot["acceptance_checks"],
    }), workspace=True)


def entry_command(root, container, candidate, entry):
    paths = {f["path"] for f in candidate["files"]}
    if entry not in paths or not re.fullmatch(r"src/[A-Za-z0-9_./-]+\.(py|js|cjs|mjs)", entry):
        raise ValueError("Select a reviewed Python or Node.js entry point")
    command = isolated_test_command(root, container)
    if entry.endswith(".py"):
        return command[:-2] + ["-B", "/work/" + entry]
    return command[:-4] + ["node:22-alpine", "node", "/work/" + entry]


def execute_entry(candidate, entry, on_output, stop_requested, timeout=90):
    from threading import Thread
    from time import monotonic

    candidate = verify_persisted_candidate(candidate, workspace=True)
    container = "ago-test-" + uuid4().hex
    with tempfile.TemporaryDirectory(prefix="ago-terminal-") as temp:
        root = Path(temp) / "work"
        stage_candidate(candidate, root, workspace=True)
        for path in [root, *root.rglob("*")]:
            os.chmod(path, 0o755 if path.is_dir() else 0o644)
        command = entry_command(root, container, candidate, entry)
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                       stdin=subprocess.DEVNULL)
        except OSError:
            return {"status": "runner_unavailable", "exit_code": None, "output": ""}
        buffer = bytearray()

        def drain():
            while chunk := process.stdout.read1(4096):
                buffer.extend(chunk)
                del buffer[:-16384]

        reader = Thread(target=drain, daemon=True)
        reader.start()
        deadline = monotonic() + timeout
        status = "completed"
        last_output = None
        try:
            while process.poll() is None:
                if stop_requested() or monotonic() >= deadline:
                    status = "timeout" if monotonic() >= deadline else "stopped"
                    break
                output = bytes(buffer).decode("utf-8", "replace")
                if output != last_output:
                    on_output(output)
                    last_output = output
                try:
                    process.wait(timeout=0.5)
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.kill()
                process.wait()
                # A stop can arrive while Docker is still creating the container.
                subprocess.run(["docker", "rm", "-f", container], timeout=10,
                               capture_output=True, check=False)
            reader.join(timeout=2)
            process.stdout.close()
        if status == "completed" and process.returncode:
            status = "runner_unavailable" if process.returncode == 125 else "failed"
        return {"status": status, "exit_code": process.returncode,
                "output": bytes(buffer).decode("utf-8", "replace")}
