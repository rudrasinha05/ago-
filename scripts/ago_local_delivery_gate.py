"""One deliberate local engineering handoff: Board output -> Docker -> pending QA.

By default this command only previews an already stored fully-cleared Board
candidate. --apply requires the human operator to have reviewed the exact
source and grants permission to run those untrusted tests in offline Docker.
No GitHub writes, signed QA verdict, cloud access or publication can occur.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ago.company_engineering import draft_github_commit_operation, stage_candidate
from ago_engineering_candidate import inspect as inspect_run
from ago_qa_review_packet import packet
from ago_verify_candidate import CONFIRM, verify

APPLY_CONFIRM = "STAGE_TEST_AND_PREPARE_QA"


def prepare(
    input_path: Path, staged_directory: Path, qa_packet_path: Path,
    *, apply: bool = False, confirm: str = "",
    github_options: tuple[str | None, ...] = (None, None, None, None),
) -> dict:
    candidate = inspect_run(input_path)
    if len(github_options) != 4:
        raise ValueError("Four exact GitHub draft fields required")
    draft = None
    if any(github_options):
        if not all(github_options):
            raise ValueError("Complete GitHub draft identity and head SHA required")
        draft = draft_github_commit_operation(
            candidate, project_id=github_options[0], operation_id=github_options[1],
            expected_sha=github_options[2], message=github_options[3],
        )
    summary = {
        "candidate_sha256": candidate["candidate_sha256"],
        "candidate_files": [x["path"] for x in candidate["files"]],
        "board_review_verified_from_local_receipt": True,
        "mode": "inspection_only",
        "tests_executed": False,
        "independent_qa_approved": False,
        "github_committed": False,
        "release_ready": False,
    }
    if not apply:
        return summary
    if confirm != APPLY_CONFIRM:
        raise PermissionError("Operator must explicitly confirm reviewed local source")
    if staged_directory.exists() or staged_directory.is_symlink():
        raise FileExistsError("Use a new empty candidate review directory")
    if qa_packet_path.exists() or qa_packet_path.is_symlink():
        raise FileExistsError("Use a new independent QA packet output path")
    if qa_packet_path.resolve().is_relative_to(staged_directory.resolve()):
        raise PermissionError("QA packet must be stored outside staged candidate")
    if not qa_packet_path.parent.is_dir():
        raise ValueError("QA packet parent directory must already exist")
    stage_candidate(candidate, staged_directory)
    if draft:
        with (staged_directory / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").open(
            "x", encoding="utf-8",
        ) as stream:
            json.dump(draft, stream, indent=2, sort_keys=True)
    # Docker is explicitly authorized in this operator call only.
    receipt = verify(staged_directory, apply=True, confirm=CONFIRM)
    summary.update(mode="local_container_test_completed",
                   tests_executed=receipt["tests_executed"],
                   local_unit_tests_passed=receipt["tests_passed"],
                   test_case_count=receipt["unittest_cases"])
    if not receipt["tests_passed"]:
        summary["next_gate"] = "Test failure: restage a new candidate after manual inspection"
        return summary
    handoff = packet(staged_directory)
    with qa_packet_path.open("x", encoding="utf-8") as stream:
        json.dump(handoff, stream, indent=2, sort_keys=True)
    summary["mode"] = "pending_independent_human_qa"
    summary["qa_packet_prepared"] = True
    summary["qa_packet_candidate_sha256"] = handoff["candidate_sha256"]
    summary["next_gate"] = "Separate authenticated human QA, not automatic GitHub dispatch"
    return summary


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--staged-directory", type=Path, required=True)
    parser.add_argument("--qa-output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--github-project-id")
    parser.add_argument("--github-operation-id")
    parser.add_argument("--github-expected-sha")
    parser.add_argument("--github-message")
    args = parser.parse_args(argv)
    try:
        result = prepare(
            args.input, args.staged_directory, args.qa_output,
            apply=args.apply, confirm=args.confirm,
            github_options=(args.github_project_id, args.github_operation_id,
                            args.github_expected_sha, args.github_message),
        )
    except (ValueError, TypeError, KeyError, RuntimeError,
            PermissionError, OSError) as exc:
        print(json.dumps({
            "status": "blocked", "reason": str(exc),
            "independent_qa_approved": False, "release_ready": False,
        }), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if not args.apply or result.get("qa_packet_prepared") else 1


if __name__ == "__main__":
    sys.exit(main())
