"""One deliberate local engineering handoff: Board output -> Docker -> pending QA.

By default this command only previews an already stored fully-cleared Board
candidate. --apply requires the human operator to have reviewed the exact
source and grants permission to run those untrusted tests in offline Docker.
No GitHub writes, signed QA verdict, cloud access or publication can occur.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from ago.company_engineering import draft_github_commit_operation, stage_candidate
from ago_engineering_candidate import inspect as inspect_run
from ago_local_repair_proposal import original_failed_candidate
from ago_qa_review_packet import packet
from ago_verify_candidate import CONFIRM, verify

APPLY_CONFIRM = "STAGE_TEST_AND_PREPARE_QA"


def inspect_local_input(input_path: Path, repair_from: Path | None) -> tuple[dict, str]:
    """Validate exact failed-source lineage before a repaired code retest."""
    candidate = inspect_run(input_path)
    document = json.loads(input_path.read_text(encoding="utf-8"))
    if document.get("kind") != "ago_unapproved_local_repair_proposal":
        if repair_from is not None:
            raise PermissionError("Only an unapproved repair proposal may set --repair-from")
        kind = "board_record" if "result" in document else "direct_unapproved_candidate"
        return candidate, kind
    if repair_from is None:
        raise PermissionError("An unapproved AI repair requires original --repair-from evidence")
    if set(document) != {
        "kind", "original_candidate_sha256", "engineering_candidate",
        "source_tests_preserved", "requires_new_local_docker_test",
        "requires_independent_human_qa", "qa_approved",
        "github_write_authorized", "release_ready", "automated_retry_executed",
    }:
        raise PermissionError("Repair request must contain exact unapproved fields")
    for key in ("source_tests_preserved", "requires_new_local_docker_test",
                "requires_independent_human_qa"):
        if document.get(key) is not True:
            raise PermissionError("Repair must retain all source and review gates")
    for key in ("qa_approved", "github_write_authorized",
                "release_ready", "automated_retry_executed"):
        if document.get(key) is not False:
            raise PermissionError("Repair proposal cannot claim authorization or execution")
    original = original_failed_candidate(repair_from)
    if document.get("original_candidate_sha256") != original["candidate_sha256"]:
        raise PermissionError("Original failed candidate digest does not match repair")
    old = {item["path"]: item["content"] for item in original["files"]}
    new = {item["path"]: item["content"] for item in candidate["files"]}
    if set(old) != set(new) or candidate["acceptance_checks"] != original["acceptance_checks"]:
        raise PermissionError("Repair cannot replace original files or acceptance checks")
    if any(old[path] != content for path, content in new.items()
           if not path.startswith("src/")):
        raise PermissionError("Repair cannot alter existing tests or documentation")
    if not any(old[path] != content for path, content in new.items()
               if path.startswith("src/")):
        raise PermissionError("Repair must contain a genuine source-only change")
    return candidate, "repair_pending_retest"


def prepare(
    input_path: Path, staged_directory: Path, qa_packet_path: Path,
    *, apply: bool = False, confirm: str = "",
    github_options: tuple[str | None, ...] = (None, None, None, None),
    repair_from: Path | None = None,
    expected_candidate_sha256: str | None = None,
) -> dict:
    candidate, input_kind = inspect_local_input(input_path, repair_from)
    if (expected_candidate_sha256 is not None
            and (not isinstance(expected_candidate_sha256, str)
                 or re.fullmatch(r"[0-9a-f]{64}", expected_candidate_sha256) is None
                 or candidate["candidate_sha256"] != expected_candidate_sha256)):
        raise PermissionError("Source digest no longer matches Founder-reviewed candidate")
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
        # A repaired proposal is NOT a newly approved Board decision.
        "input_kind": input_kind,
        "board_review_verified_from_local_receipt": input_kind == "board_record",
        "repair_source_lineage_checked": input_kind == "repair_pending_retest",
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
    parser.add_argument("--repair-from", type=Path)
    parser.add_argument("--expected-candidate-sha256")
    args = parser.parse_args(argv)
    try:
        result = prepare(
            args.input, args.staged_directory, args.qa_output,
            apply=args.apply, confirm=args.confirm,
            github_options=(args.github_project_id, args.github_operation_id,
                            args.github_expected_sha, args.github_message),
            repair_from=args.repair_from,
            expected_candidate_sha256=args.expected_candidate_sha256,
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
