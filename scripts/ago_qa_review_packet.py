"""Prepare an unprivileged independent-QA review request from staged local code.

No network, model inference, GitHub dispatch or implicit approval. A local
receipt is only *untrusted evidence* and can be fabricated by its owner; the
actual human QA decision must be authenticated and persisted by AGO governance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from ago_verify_candidate import inspect

KIND = "ago_independent_qa_review_request"
RECEIPT_KIND = "ago_local_container_unittest_receipt"


def packet(directory: str | Path) -> dict:
    root = Path(directory)
    evidence = inspect(root)
    path = root / "AGO_TEST_RECEIPT.json"
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 16384:
        raise ValueError("Small, regular staged local test receipt required")
    raw = path.read_bytes()
    result = json.loads(raw)
    if not isinstance(result, dict) or result.get("kind") != RECEIPT_KIND:
        raise ValueError("Exact local container test receipt required")
    if (result.get("candidate_sha256") != evidence["candidate_sha256"]
            or result.get("tests_executed") is not True
            or result.get("tests_passed") is not True
            or type(result.get("unittest_cases")) is not int
            or result["unittest_cases"] < 1
            or type(result.get("docker_exit_code")) is not int
            or result["docker_exit_code"] != 0
            or result.get("network_disabled") is not True
            or result.get("read_only_container") is not True
            or result.get("git_committed") is not False
            or result.get("independent_qa_approved") is not False
            or result.get("release_ready") is not False):
        raise PermissionError("Staged test receipt does not prove even local passing smoke")
    draft = root / "AGO_UNSUBMITTED_GITHUB_OPERATION.json"
    operation = json.loads(draft.read_text(encoding="utf-8")) if draft.exists() else None
    # inspect() has already compared the exact draft files against the staged
    # source. The draft is not an approved dispatch operation.
    return {
        "kind": KIND,
        "candidate_sha256": evidence["candidate_sha256"],
        "local_test_receipt_sha256": hashlib.sha256(raw).hexdigest(),
        "unittest_cases": result["unittest_cases"],
        "files": evidence["files"],
        "acceptance_checks": evidence["acceptance_checks"],
        "proposed_github_operation_id": operation["id"] if operation else None,
        "test_evidence_only": True,
        "independent_human_qa_pending": True,
        "qa_approved": False,
        "github_write_authorized": False,
        "release_ready": False,
        "untrusted_local_receipt": True,
        "next_gate": "Authenticated separate human QA review in AGO and verified source digest",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--staged-directory", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        result = packet(args.staged_directory)
        if args.apply:
            if args.confirm != "PREPARE_INDEPENDENT_QA_REVIEW":
                raise PermissionError("Explicit QA review packet creation confirmation required")
            if args.output is None:
                raise ValueError("Explicit new QA packet destination required")
            root = args.staged_directory.resolve()
            destination = args.output.resolve()
            if destination.is_relative_to(root):
                raise PermissionError("QA packet must not alter staged candidate")
            with args.output.open("x", encoding="utf-8") as stream:
                json.dump(result, stream, indent=2, sort_keys=True)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, TypeError, KeyError, PermissionError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc),
                          "qa_approved": False, "release_ready": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
