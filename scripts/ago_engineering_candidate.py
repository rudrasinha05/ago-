"""Founder-controlled offline staging of exact AI engineering candidates.

Read only by default. Explicit write creates one new review directory;
never runs code, installs dependencies, writes Git history or invokes GitHub.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ago.company_engineering import (
    draft_github_commit_operation,
    stage_candidate,
    verify_persisted_candidate,
)


def inspect(path: Path) -> dict:
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 40000:
        raise ValueError("Small regular local JSON file required")
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise TypeError("AGO run result must be a JSON object")
    # Supports a copied agent run receipt or a direct review candidate.
    result = document.get("result", document)
    if not isinstance(result, dict):
        raise TypeError("AGO run result must contain one object")
    if "result" in document and result.get("board_review_cleared") is not True:
        raise PermissionError("Source staging requires the complete approving AI Board record")
    value = result.get("engineering_candidate", result)
    return verify_persisted_candidate(value)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AGO unexecuted source candidate review")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--github-project-id")
    parser.add_argument("--github-operation-id")
    parser.add_argument("--github-expected-sha")
    parser.add_argument("--github-message")
    args = parser.parse_args(argv)
    try:
        candidate = inspect(args.input)
        report = {
            "candidate_sha256": candidate["candidate_sha256"],
            "paths": [item["path"] for item in candidate["files"]],
            "python_syntax_checked": candidate["source_parse_passed"],
            "tests_executed": False,
            "git_committed": False,
            "mode": "dry_run",
        }
        github_options = (
            args.github_project_id, args.github_operation_id,
            args.github_expected_sha, args.github_message,
        )
        draft = None
        if any(github_options):
            if not all(github_options):
                raise ValueError("All four exact GitHub draft operation options required")
            draft = draft_github_commit_operation(
                candidate,
                project_id=args.github_project_id,
                operation_id=args.github_operation_id,
                expected_sha=args.github_expected_sha,
                message=args.github_message,
            )
            report["github_draft_ready"] = True
            report["github_submitted"] = False
        if args.apply:
            if args.confirm != "WRITE_REVIEWED_CANDIDATE":
                raise PermissionError("Explicit review destination confirmation required")
            stage_candidate(candidate, args.output)
            if draft:
                with (args.output / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").open(
                    "x", encoding="utf-8"
                ) as stream:
                    json.dump(draft, stream, indent=2, sort_keys=True)
            report["mode"] = "files_staged_for_human_review"
        print(json.dumps(report, sort_keys=True))
        return 0
    except (ValueError, TypeError, PermissionError, FileExistsError, OSError, KeyError):
        # Avoid leaking raw untrusted code, credentials or local paths.
        print(json.dumps({"ok": False, "error": "candidate_review_failed"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
