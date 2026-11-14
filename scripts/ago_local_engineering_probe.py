"""Explicit local Ollama AI-005 code-author probe; NOT an AGO company task.

One Founder-invoked schema-constrained inference against localhost only. The
result is static reviewed source/test evidence, never code execution, an
approved Board decision, a Docker pass, GitHub delivery or a release.
Only a digest/boolean receipt is persisted; model source stays in memory.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from ago.company_engineering import (
    ENGINEERING_CANDIDATE_SCHEMA,
    assert_discoverable_unittest,
    reviewed_candidate,
)
from ago.model_provider import OllamaLocalTextProvider

CONFIRM = "PROBE_INSTALLED_ENGINEERING_MODEL"
PROMPT = (
    "This is a local AI-005 code-author capability PROBE, not an approved company "
    "task or permission to execute code. Produce ONLY one JSON object with EXACT "
    "fields files and acceptance_checks. Generate a small correct Python "
    "src/arithmetic.py implementing def add(a, b) that returns the sum, and "
    "tests/test_arithmetic.py with import unittest, from src.arithmetic import add, "
    "and at least one unittest.TestCase def test_* method that checks normal "
    "and negative integers. Use only Python standard library; no networking, "
    "commands, secrets, prose, Markdown, or fake execution results. "
    "acceptance_checks must contain one or two short test descriptions."
)


def probe(destination: Path, *, apply: bool = False, confirm: str = "",
          provider=None, clock=time.monotonic) -> dict:
    """Never contact Ollama without explicit opt-in; never persist generated code."""
    model = os.getenv("AGO_LLM_MODEL", "")
    if not model:
        raise ValueError("Explicit installed local coding model tag required")
    # Even preview validates the model name using the existing hardened adapter.
    local = provider or OllamaLocalTextProvider(
        model=model, timeout_seconds=60, max_output_tokens=1024, keep_alive="0s",
    )
    report = {
        "kind": "ago_ai005_standalone_local_code_author_probe_v1",
        "model_tag": model,
        "endpoint": OllamaLocalTextProvider.ENDPOINT,
        "mode": "inspection_only",
        "provider_called": False,
        "schema_requested": False,
        "code_candidate_static_reviewed": False,
        "model_response_persisted": False,
        "model_source_persisted": False,
        "real_ago_founder_task_executed": False,
        "board_approval_verified": False,
        "tests_executed": False,
        "independent_human_qa_approved": False,
        "github_committed": False,
        "release_ready": False,
    }
    if not apply:
        return report
    if confirm != CONFIRM:
        raise PermissionError("Explicit local engineering probe confirmation required")
    if (os.getenv("AGO_ENVIRONMENT") != "development"
            or os.getenv("AGO_LLM_PROVIDER") != "ollama_local"
            or os.getenv("AGO_ENABLE_LOCAL_MODELS") != "true"
            or os.getenv("AGO_ENABLE_PAID_MODELS", "false") != "false"):
        raise PermissionError("Explicit free local-only development settings required")
    if (destination.exists() or destination.is_symlink()
            or not destination.parent.is_dir()):
        raise FileExistsError("A new file in an existing directory is required")
    began = clock()
    if getattr(local, "supports_response_schema", False) is True:
        raw = local.generate(PROMPT, response_schema=ENGINEERING_CANDIDATE_SCHEMA)
        schema_requested = True
    else:
        raw = local.generate(PROMPT)
        schema_requested = False
    duration = clock() - began
    if not 0 <= duration <= 120:
        raise TimeoutError("Local engineering inference exceeded runtime bound")
    candidate = assert_discoverable_unittest(reviewed_candidate(raw))
    report.update(
        mode="static_candidate_reviewed",
        provider_called=True,
        schema_requested=schema_requested,
        code_candidate_static_reviewed=True,
        candidate_sha256=candidate["candidate_sha256"],
        source_file_count=sum(x["path"].startswith("src/") for x in candidate["files"]),
        test_file_count=sum(x["path"].startswith("tests/test_") for x in candidate["files"]),
        # An injected test provider is never proof of real local Ollama inference.
        local_ollama_response_observed=provider is None,
        elapsed_seconds=round(duration, 3),
    )
    # No model output, code, private project brief, or credentials are stored.
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    args = parser.parse_args(argv)
    try:
        result = probe(args.output, apply=args.apply, confirm=args.confirm)
    except (ValueError, TypeError, KeyError, RuntimeError, TimeoutError,
            PermissionError, FileExistsError, OSError) as exc:
        # Never leak raw model output, a private brief or local provider errors.
        print(json.dumps({
            "status": "blocked",
            "error_type": type(exc).__name__,
            "real_ago_founder_task_executed": False,
            "release_ready": False,
        }), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
