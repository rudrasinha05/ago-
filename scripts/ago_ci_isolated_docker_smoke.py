"""Trusted CI-only real-Docker smoke for the reviewed candidate QA boundary.

This is NOT model-generated code or a credential-backed AGO task. The two
fixed examples intentionally exercise real Docker with successful and failing
unittest cases. This module must never run as an API hook or an import side
effect. It does not create a project release, PR, or independent QA verdict.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from ago.company_engineering import reviewed_candidate, stage_candidate
from ago_verify_candidate import CONFIRM, verify


def candidate_source(*, broken: bool) -> dict:
    return {
        "files": [
            {
                "path": "src/arithmetic.py",
                "content": ("def multiply(a, b):\n    return a + b\n"
                            if broken else
                            "def multiply(a, b):\n    return a * b\n"),
            },
            {
                "path": "tests/test_arithmetic.py",
                "content": (
                    "import unittest\n"
                    "from src.arithmetic import multiply\n"
                    "class ArithmeticTests(unittest.TestCase):\n"
                    "    def test_multiplication(self):\n"
                    "        self.assertEqual(multiply(3, 4), 12)\n"
                    "    def test_zero(self):\n"
                    "        self.assertEqual(multiply(0, 7), 0)\n"
                ),
            },
        ],
        "acceptance_checks": ["Multiply integers correctly", "Zero multiplier returns zero"],
    }


def exercise(*, broken: bool) -> dict:
    # tempfile creates mode 0700 directories. The read-only, non-root Docker
    # worker needs traversal permission to read the expressly staged contents.
    with tempfile.TemporaryDirectory(prefix="ago-ci-trusted-") as temp:
        root = Path(temp)
        root.chmod(0o755)
        location = root / "staged"
        candidate = reviewed_candidate(json.dumps(candidate_source(broken=broken)))
        stage_candidate(candidate, location)
        location.chmod(0o755)
        preview = verify(location)
        assert preview["tests_executed"] is False
        assert preview["candidate_sha256"] == candidate["candidate_sha256"]
        result = verify(location, apply=True, confirm=CONFIRM, timeout=90)
        receipt = json.loads((location / "AGO_TEST_RECEIPT.json").read_text(encoding="utf-8"))
        assert result == receipt, "CI smoke failed to persist exact receipt"
        assert result["candidate_sha256"] == candidate["candidate_sha256"]
        assert result["network_disabled"] is True
        assert result["read_only_container"] is True
        assert result["independent_qa_approved"] is False
        assert result["git_committed"] is False
        assert result["release_ready"] is False
        assert result["unittest_cases"] == 2
        assert result["tests_executed"] is True
        assert result["tests_passed"] is not broken
        return {
            "scenario": "known_broken" if broken else "known_correct",
            "candidate_sha256": result["candidate_sha256"],
            "unittest_cases": result["unittest_cases"],
            "tests_passed": result["tests_passed"],
            "release_ready": result["release_ready"],
            "independent_qa_approved": result["independent_qa_approved"],
        }


def main() -> None:
    passed = exercise(broken=False)
    failed = exercise(broken=True)
    assert passed["candidate_sha256"] != failed["candidate_sha256"]
    print(json.dumps({"kind": "ago_ci_real_docker_smoke",
                      "trusted_static_fixture_only": True,
                      "passing_fixture": passed,
                      "failing_fixture": failed,
                      "live_model_execution_proved": False,
                      "external_git_write_proved": False,
                      "released": False}, sort_keys=True))


if __name__ == "__main__":
    main()
