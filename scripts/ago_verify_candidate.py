"""Explicit, local-only Docker QA smoke for a human-staged AGO Python candidate.

Never runs on import or from the API. A staged candidate is NOT trusted code;
Docker's default isolation is not a security certification. Requires a local,
preloaded python:3.11-slim image and a founder/operator's exact opt-in.
Never uses host Python to execute candidate files, downloads, GitHub or cloud.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

from ago.company_engineering import reviewed_candidate
from ago.github_adapter import validate_operation

CONFIRM = "EXECUTE_LOCAL_ISOLATED_TESTS"
IMAGE = "python:3.11-slim"
MARKER = "AGO_UNITTEST_CASES="
# unittest accepts only TestCase tests, deliberately not arbitrary pytest plugins.
RUNNER = (
    "import sys,unittest;"
    "suite=unittest.defaultTestLoader.discover('tests',pattern='test_*.py');"
    "n=suite.countTestCases();print('AGO_UNITTEST_CASES='+str(n),flush=True);"
    "sys.exit(4) if n==0 else "
    "sys.exit(0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1)"
)


def inspect(directory: str | Path) -> dict:
    root = Path(directory)
    if not root.is_dir() or root.is_symlink():
        raise ValueError("An existing, non-symlink staged review directory is required")
    manifest_path = root / "AGO_REVIEW_MANIFEST.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("Staged review manifest is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected = manifest.get("file_evidence")
    checks = manifest.get("acceptance_checks")
    if not isinstance(expected, list) or not isinstance(checks, list):
        raise TypeError("Reviewed file evidence and acceptance criteria required")
    files = []
    known = {"AGO_REVIEW_MANIFEST.json", "AGO_TEST_RECEIPT.json",
             "AGO_UNSUBMITTED_GITHUB_OPERATION.json"}
    for item in expected:
        path = item.get("path") if isinstance(item, dict) else None
        if not isinstance(path, str) or path.startswith("/") or ".." in path.split("/"):
            raise PermissionError("Untrusted staged source path")
        target = root.joinpath(*path.split("/"))
        if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root.resolve()):
            raise PermissionError("Staged source was moved, linked or removed")
        code = target.read_text(encoding="utf-8")
        if hashlib.sha256(code.encode("utf-8")).hexdigest() != item.get("sha256"):
            raise PermissionError("Staged file bytes differ from reviewed evidence")
        files.append({"path": path, "content": code})
        known.add(path)
    # Do not mount undocumented files, including symlinks or compiled payloads.
    for found in root.rglob("*"):
        if found.is_symlink():
            raise PermissionError("Staged candidate contains an unexpected symlink")
        if found.is_file() and found.relative_to(root).as_posix() not in known:
            raise PermissionError("Unreviewed file present in staged candidate")
    candidate = reviewed_candidate(json.dumps({"files": files, "acceptance_checks": checks}))
    if (candidate["candidate_sha256"] != manifest.get("candidate_sha256")
            or candidate["file_evidence"] != expected):
        raise PermissionError("Staged candidate/manifest integrity mismatch")
    # The optional, review-only GitHub draft may accompany a staged candidate.
    # Never accept a draft that contains different or additional source bytes.
    github_path = root / "AGO_UNSUBMITTED_GITHUB_OPERATION.json"
    if github_path.exists():
        if github_path.is_symlink() or not github_path.is_file():
            raise PermissionError("Invalid staged GitHub draft")
        draft = json.loads(github_path.read_text(encoding="utf-8"))
        validate_operation(draft)
        if (draft["operation"] != "commit_files"
                or draft["payload"]["files"] != candidate["files"]):
            raise PermissionError("GitHub draft source differs from reviewed candidate")
    return {"candidate_sha256": candidate["candidate_sha256"],
            "files": [x["path"] for x in files], "acceptance_checks": checks,
            "tests_executed": False, "sandbox_verified": False}


def docker_command(root: Path, container_name: str) -> list[str]:
    if not re.fullmatch(r"ago-qa-[a-f0-9]{32}", container_name):
        raise ValueError("Randomly isolated candidate container identifier required")
    return [
        "docker", "run", "--rm", "--pull=never",
        "--name", container_name, "--network", "none", "--read-only",
        "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=64", "--memory=256m", "--cpus=1",
        "--user=65534:65534", "--tmpfs=/tmp:rw,noexec,nosuid,size=64m",
        "--mount", "type=bind,src=" + str(root.resolve()) + ",dst=/work,readonly",
        "--workdir=/work", "--env=PYTHONPATH=/work",
        "--env=PYTHONDONTWRITEBYTECODE=1",
        IMAGE, "python", "-c", RUNNER,
    ]


def verify(directory: str | Path, *, apply: bool = False, confirm: str | None = None,
           timeout: int = 90, runner=subprocess.run) -> dict:
    evidence = inspect(directory)
    if not apply:
        return {"status": "inspection_only", **evidence}
    if confirm != CONFIRM:
        raise PermissionError("Explicit local operator confirmation is mandatory")
    if type(timeout) is not int or not 10 <= timeout <= 300:
        raise ValueError("Test timeout must be 10..300 seconds")
    root = Path(directory)
    receipt_path = root / "AGO_TEST_RECEIPT.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        raise FileExistsError("A previous test receipt exists; stage a new candidate")
    container = "ago-qa-" + uuid4().hex
    command = docker_command(root, container)
    try:
        result = runner(command, capture_output=True, text=True,
                        timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        # Unknown execution outcome must not be silently retried or marked passed.
        subprocess.run(["docker", "rm", "-f", container], capture_output=True,
                       text=True, timeout=15, check=False)
        raise RuntimeError("Local test timed out; inspect Docker and restage before retry") from exc
    output = str(result.stdout or "") + "\n" + str(result.stderr or "")
    seen = re.findall(r"(?:^|\n)AGO_UNITTEST_CASES=(\d+)(?:\r?\n|$)", output)
    count = int(seen[0]) if len(seen) == 1 else 0
    passed = result.returncode == 0 and count >= 1
    receipt = {
        "kind": "ago_local_container_unittest_receipt",
        "candidate_sha256": evidence["candidate_sha256"],
        "tests_executed": count >= 1,
        "tests_passed": passed,
        "unittest_cases": count,
        "docker_exit_code": result.returncode,
        "network_disabled": True,
        "read_only_container": True,
        "git_committed": False,
        "independent_qa_approved": False,
        "release_ready": False,
        "output_excerpt": output[-2500:],
    }
    with receipt_path.open("x", encoding="utf-8") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True)
    return receipt


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged-directory", required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm")
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args(argv)
    try:
        result = verify(args.staged_directory, apply=args.apply,
                        confirm=args.confirm, timeout=args.timeout)
    except (OSError, ValueError, RuntimeError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc),
                          "tests_passed": False}), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if not args.apply or result["tests_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
