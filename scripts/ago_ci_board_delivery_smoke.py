"""Fixed-fixture full-board -> engineering -> real Docker -> pending QA smoke.

Use only on trusted disposable CI runners. The Board and code generator are
synthetic fixtures, not a live Ollama account or independently staffed company.
GitHub operations are drafted but NEVER sent. Human QA and release remain false.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

from ago.company_engineering import (
    draft_github_commit_operation,
    stage_candidate,
    verify_persisted_candidate,
)
from ago.company_ollama_chain import FULL_BOARD_STAGES, run_four_role_chain
from ago_ci_isolated_docker_smoke import candidate_source
from ago_qa_review_packet import packet
from ago_verify_candidate import CONFIRM, verify


class FixedBoardProvider:
    def __init__(self, *, deny_risk: bool = False, broken_code: bool = False):
        self.deny_risk = deny_risk
        self.broken_code = broken_code
        self.calls = []

    def generate(self, prompt: str) -> str:
        self.calls.append(prompt)
        if "ROLE: EMPLOYEE\n" in prompt:
            return json.dumps(candidate_source(broken=self.broken_code))
        if "ROLE: RISK\n" in prompt and self.deny_risk:
            return "BOARD_RECOMMENDATION: DENY\nRISKS: Static fixture veto"
        if "BOARD_ADVISORY:" in prompt:
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: Static fixture only"
        return "DECISION: Fixture scoped plan, no external actions"


def board_result(provider: FixedBoardProvider) -> dict:
    task = SimpleNamespace(
        id=str(uuid4()),
        project_context={
            "intake_id": str(uuid4()),
            "title": "Synthetic QA contract, not a real Founder project",
            "brief": "Create only an offline arithmetic demonstration; no live execution authority.",
        },
    )
    participants = [
        {"role": role, "employee_id": str(uuid4()), "employee_name": role.upper()}
        for role, _, _ in FULL_BOARD_STAGES
    ]
    return run_four_role_chain(
        task=task, participants=participants, provider=provider,
        engineering_candidates=True,
    )


def exercise(*, broken: bool = False) -> dict:
    provider = FixedBoardProvider(broken_code=broken)
    result = board_result(provider)
    assert result["board_review_cleared"] is True
    assert result["board_recommendations_binding"] is False
    assert result["handoff_complete"] is True
    assert result["roles_completed"] == 7
    assert len(provider.calls) == 7
    assert result["github_commits_created"] is False
    assert result["project_released"] is False
    candidate = verify_persisted_candidate(result["engineering_candidate"])

    with tempfile.TemporaryDirectory(prefix="ago-ci-board-") as temp:
        root = Path(temp)
        root.chmod(0o755)
        staged = root / "candidate"
        stage_candidate(candidate, staged)
        staged.chmod(0o755)
        op = draft_github_commit_operation(
            candidate, project_id=str(uuid4()), operation_id=str(uuid4()),
            expected_sha="a" * 40,
            message="Static fixture SHA review; not a real GitHub operation",
        )
        (staged / "AGO_UNSUBMITTED_GITHUB_OPERATION.json").write_text(
            json.dumps(op), encoding="utf-8",
        )
        preview = verify(staged)
        assert preview["candidate_sha256"] == candidate["candidate_sha256"]
        assert preview["tests_executed"] is False
        receipt = verify(staged, apply=True, confirm=CONFIRM, timeout=90)
        assert receipt["tests_executed"] is True
        assert receipt["unittest_cases"] == 2
        assert receipt["tests_passed"] is (not broken)
        assert receipt["independent_qa_approved"] is False
        assert receipt["release_ready"] is False
        if broken:
            try:
                packet(staged)
            except PermissionError:
                return {
                    "scenario": "broken_code",
                    "real_docker_tests_passed": False,
                    "qa_packet_blocked": True,
                    "github_committed": False,
                    "released": False,
                }
            raise AssertionError("A broken board code candidate reached QA packet")
        handoff = packet(staged)
        assert handoff["candidate_sha256"] == candidate["candidate_sha256"]
        assert handoff["proposed_github_operation_id"] == op["id"]
        assert handoff["unittest_cases"] == 2
        assert handoff["qa_approved"] is False
        assert handoff["github_write_authorized"] is False
        assert handoff["release_ready"] is False
        return {
            "scenario": "passing_code",
            "real_docker_tests_passed": True,
            "qa_packet_pending": handoff["independent_human_qa_pending"],
            "github_draft_validated": True,
            "github_committed": False,
            "released": False,
        }


def test_veto_stops_code_generation() -> dict:
    provider = FixedBoardProvider(deny_risk=True)
    result = board_result(provider)
    assert result["board_blocked"] is True
    assert result["blocked_by_board_seat"] == "Risk & Compliance"
    assert result["engineering_candidate"] is None
    assert result["handoff_complete"] is False
    assert len(provider.calls) == 4
    return {"board_veto_prevented_engineering": True, "github_committed": False}


def main() -> None:
    veto = test_veto_stops_code_generation()
    passing = exercise()
    failing = exercise(broken=True)
    print(json.dumps({
        "kind": "ago_ci_synthetic_board_to_pending_qa",
        "trusted_fixed_fixtures_only": True,
        "board_veto": veto,
        "passing": passing,
        "failing": failing,
        "live_ollama_verified": False,
        "independent_human_qa_approved": False,
        "ago_owned_github_commit_verified": False,
        "release_ready": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
