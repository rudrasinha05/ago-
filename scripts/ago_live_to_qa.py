"""Founder-controlled bridge: persisted REAL Ollama run -> offline Docker -> QA.

Reads a completed governed run through signed localhost AGO APIs. Never asks
the model to write directly to disk, never performs an automatic repair, never
grants QA approval and never contacts GitHub. The independent human verdict
and separately approved GitHub operation remain distinct later phases.

Preview uses read-only localhost requests. --apply needs two explicit, different
consents and writes only new private files outside the AGO Git checkout. After
any partial failure, inspect the local receipts; NEVER automatically replay.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path
from urllib.request import urlopen
from uuid import UUID

from ago_local_delivery_gate import APPLY_CONFIRM as DOCKER_CONFIRM, prepare
from ago_pull_candidate import (
    CONFIRM as EXPORT_CONFIRM,
    export_from_founder_session,
)
from local_approved_agent_batch import founder_login, local_url


def _private_paths(export: Path, staged: Path, qa_packet: Path) -> None:
    repo = Path(__file__).resolve().parents[1]
    paths = (export, staged, qa_packet)
    resolved = [p.resolve() for p in paths]
    if len(set(resolved)) != 3:
        raise PermissionError("Distinct private export, stage and QA paths required")
    if (resolved[0].is_relative_to(resolved[1])
            or resolved[2].is_relative_to(resolved[1])):
        raise PermissionError("Export and QA packet must stay outside untrusted stage")
    for path, exact in zip(paths, resolved, strict=True):
        if exact.is_relative_to(repo) or path.is_symlink():
            raise PermissionError("Delivery artifacts must stay outside AGO checkout")
        if not path.parent.is_dir():
            raise ValueError("Pre-existing private output parent directory required")
        if path.exists():
            raise FileExistsError("Never overwrite or replay an existing receipt")


def bridge(
    run_id: str, export: Path, staged: Path, qa_packet: Path,
    *, base: str, token: str, apply: bool = False,
    confirm_export: str = "", confirm_docker: str = "", opener=urlopen,
) -> dict:
    """A bounded one-run operation; fail closed before every write."""
    UUID(run_id)
    base = local_url(base)
    if apply and (confirm_export != EXPORT_CONFIRM
                  or confirm_docker != DOCKER_CONFIRM):
        raise PermissionError("Separate export and Docker confirmations required")
    _private_paths(export, staged, qa_packet)
    preview = export_from_founder_session(
        base, token, run_id, export, opener=opener,
    )
    report = {
        "mode": "read_only_preview",
        "run_id": preview["run_id"],
        "task_id": preview["task_id"],
        "project_id": preview["project_id"],
        "candidate_sha256": preview["candidate_sha256"],
        "file_count": preview["file_count"],
        "local_ollama_execution_claim": "existing_persisted_run_only",
        "docker_tests_executed": False,
        "independent_human_qa_approved": False,
        "github_operation_submitted": False,
        "github_committed": False,
        "release_ready": False,
    }
    if not apply:
        return report
    # Export only a *real*, server-persisted 7-role Board-cleared run.
    exported = export_from_founder_session(
        base, token, run_id, export, apply=True,
        confirm=EXPORT_CONFIRM, opener=opener,
    )
    if any(exported[key] != preview[key] for key in (
        "run_id", "task_id", "project_id", "candidate_sha256",
    )):
        raise PermissionError("Authenticated run changed during export; no Docker run")
    # The existing gateway supplies the full source/path/hash validation,
    # network-disabled read-only Docker, unittest receipt and QA packet.
    tested = prepare(
        export, staged, qa_packet, apply=True, confirm=DOCKER_CONFIRM,
        expected_candidate_sha256=preview["candidate_sha256"],
    )
    report.update(
        mode=tested["mode"],
        docker_tests_executed=tested["tests_executed"],
        docker_unittest_cases=tested.get("test_case_count", 0),
        docker_tests_passed=tested.get("local_unit_tests_passed", False),
        qa_packet_prepared=tested.get("qa_packet_prepared", False),
        next_gate=tested["next_gate"],
    )
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--local-url", default="http://127.0.0.1:8000")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--staged-directory", type=Path, required=True)
    parser.add_argument("--qa-packet", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm-export", default="")
    parser.add_argument("--confirm-docker", default="")
    a = parser.parse_args(argv)
    try:
        # Wrong write confirmations never even prompt for credentials or
        # create network requests, stage directories or Docker containers.
        if a.apply and (a.confirm_export != EXPORT_CONFIRM
                        or a.confirm_docker != DOCKER_CONFIRM):
            raise PermissionError("Two separate exact confirmations required")
        base = local_url(a.local_url)
        tenant = input("AGO organization ID: ").strip()
        email = input("Founder work email: ").strip()
        password = getpass.getpass("Founder password (hidden): ")
        token = founder_login(base, tenant, email, password)
        del password
        report = bridge(
            a.run_id, a.export, a.staged_directory, a.qa_packet,
            base=base, token=token, apply=a.apply,
            confirm_export=a.confirm_export,
            confirm_docker=a.confirm_docker,
        )
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "github_committed": False}))
        return 130
    except (OSError, ValueError, TypeError, KeyError,
            PermissionError, RuntimeError) as exc:
        # No private candidate text, credentials, raw errors or local paths.
        print(json.dumps({
            "status": "blocked", "error_type": type(exc).__name__,
            "github_committed": False, "release_ready": False,
        }), file=sys.stderr)
        return 2
    print(json.dumps(report, sort_keys=True))
    return 0 if not a.apply or report.get("qa_packet_prepared") else 1


if __name__ == "__main__":
    raise SystemExit(main())
