"""Founder-invoked proof of actual localhost model inference, never simulated.

The only network destination is 127.0.0.1:11434; no credentials, tools,
model pull, subprocesses, proxy, file writes or autonomous service startup.
CI uses injected offline responses and cannot certify founder hardware.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

ENDPOINT = "http://127.0.0.1:11434/api/generate"
_TIMEOUT = 60
_RESPONSE_LIMIT = 16384
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}\Z")


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise PermissionError("Ollama local inference cannot redirect")


def validate_model(name: str) -> str:
    if not isinstance(name, str) or _NAME.fullmatch(name) is None:
        raise ValueError("Explicit installed local model tag required")
    return name


def probe(model: str, *, opener=None, clock=None) -> dict:
    """Perform precisely one bounded, read-only model generation on localhost."""
    name = validate_model(model)
    clock = clock or time.monotonic
    transport = opener or build_opener(ProxyHandler({}), NoRedirect()).open
    body = {
        "model": name,
        "prompt": "AGO local-only readiness probe. Reply with one simple word: READY.",
        "stream": False,
        "keep_alive": "0s",
        "options": {"num_ctx": 512, "num_predict": 16, "temperature": 0},
    }
    request = Request(
        ENDPOINT, method="POST", data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    started = clock()
    with transport(request, timeout=_TIMEOUT) as response:
        if getattr(response, "status", None) != 200:
            raise RuntimeError("Local Ollama readiness endpoint failed")
        raw = response.read(_RESPONSE_LIMIT + 1)
    elapsed = clock() - started
    if not 0 <= elapsed <= _TIMEOUT or len(raw) > _RESPONSE_LIMIT:
        raise TimeoutError("Local inference exceeded its verified resource window")
    payload = json.loads(raw)
    if (not isinstance(payload, dict) or payload.get("done") is not True
            or payload.get("model") != name
            or not isinstance(payload.get("response"), str)
            or not payload["response"].strip()):
        raise RuntimeError("Local model has not returned a valid completed inference")
    result = {
        "kind": "ago_founder_local_inference_probe_v1",
        "verified_live_inference": True,
        "model_tag": name,
        "transport": "local_loopback_only",
        "elapsed_ms": round(elapsed * 1000),
        "response_sha256": hashlib.sha256(payload["response"].encode("utf-8")).hexdigest(),
        "response_text_persisted": False,
        "github_write_authorized": False,
        "independent_qa_completed": False,
        "hardware_verified": False,
    }
    for key in ("eval_count", "eval_duration"):
        value = payload.get(key)
        if type(value) is int and 0 <= value <= 10**15:
            result[key] = value
    return result


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen2.5-coder:1.5b")
    parser.add_argument("--confirm-live", action="store_true",
                        help="Initiate one real inference against manually started localhost Ollama")
    args = parser.parse_args(argv)
    try:
        name = validate_model(args.model)
        if not args.confirm_live:
            print(json.dumps({
                "kind": "ago_founder_local_inference_probe_v1",
                "verified_live_inference": False,
                "model_tag": name,
                "status": "dry_run_only",
                "requires_explicit_confirmation": True,
            }, sort_keys=True))
            return 0
        print(json.dumps(probe(name), sort_keys=True))
        return 0
    except (ValueError, TimeoutError, RuntimeError, OSError, KeyError, TypeError):
        # Never print local provider output, request exceptions, or private data.
        print(json.dumps({"verified_live_inference": False, "error": "local_probe_failed"}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
