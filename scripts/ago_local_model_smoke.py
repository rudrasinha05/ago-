"""Explicit, localhost-only actual Ollama inference proof for owner's Windows setup.

This is NOT an autonomous agent job, QA verdict, or proof of GPU usage.
No model install, download, service start, cloud fallback or background task.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from ago.model_provider import OllamaLocalTextProvider

CONFIRM = "TEST_INSTALLED_LOCAL_MODEL"
PROMPT = (
    "AGO personal local-model connectivity verification. "
    "Reply with a short sentence describing the number two. "
    "This request is not a company task and authorizes no tools or decisions."
)


def smoke(destination: Path, *, apply: bool = False, confirm: str = "",
          provider=None, clock=time.monotonic) -> dict:
    model = os.getenv("AGO_LLM_MODEL", "")
    if not model:
        raise ValueError("Set the exact installed local Ollama model name first")
    # Validation uses precisely the hardened loopback adapter.
    local = provider or OllamaLocalTextProvider(
        model=model, timeout_seconds=45, max_output_tokens=128, keep_alive="0s"
    )
    result = {
        "kind": "ago_local_ollama_connectivity_receipt",
        "model": model,
        "endpoint": OllamaLocalTextProvider.ENDPOINT,
        "status": "inspection_only",
        "provider_called": False,
        "real_local_inference_proved": False,
        "raw_model_output_persisted": False,
        "real_founder_project_executed": False,
        "independent_human_qa_approved": False,
        "github_committed": False,
        "release_ready": False,
    }
    if not apply:
        return result
    if confirm != CONFIRM:
        raise PermissionError("Explicit local model smoke consent required")
    if (os.getenv("AGO_LLM_PROVIDER") != "ollama_local"
            or os.getenv("AGO_ENABLE_LOCAL_MODELS") != "true"):
        raise PermissionError("Explicit local-only Ollama settings required")
    if destination.exists() or destination.is_symlink():
        raise FileExistsError("A new local proof destination is mandatory")
    if not destination.parent.is_dir():
        raise ValueError("The local proof destination parent must already exist")
    started = clock()
    output = local.generate(PROMPT)
    seconds = clock() - started
    if not isinstance(output, str) or not output.strip() or not 0 <= seconds <= 120:
        raise RuntimeError("Bounded local Ollama result or runtime invalid")
    result.update(
        status="local_model_responded",
        provider_called=True,
        # Injected providers in automated tests are explicitly not real Ollama.
        real_local_inference_proved=provider is None,
        response_digest_sha256=hashlib.sha256(output.encode("utf-8")).hexdigest(),
        response_bytes=len(output.encode("utf-8")),
        elapsed_seconds=round(seconds, 3),
        observed_at=datetime.now(UTC).isoformat(),
        proof_level="untrusted_local_operator_receipt_not_independent_attestation",
    )
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    a = parser.parse_args(argv)
    try:
        result = smoke(a.output, apply=a.apply, confirm=a.confirm)
    except (ValueError, TypeError, OSError, RuntimeError, PermissionError) as exc:
        print(json.dumps({
            "status": "blocked", "error_type": type(exc).__name__,
            "real_founder_project_executed": False, "release_ready": False,
        }), file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
