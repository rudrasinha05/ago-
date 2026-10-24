"""Fail-closed, small allowlisted security audit metadata.

An audit entry can describe which kind of event happened, not copy arbitrary
request payloads, founder briefs, tokens, prompts or nested private data.
"""
from __future__ import annotations

import re
from collections.abc import Mapping

_SAFE_KEY = re.compile(
    r"^(?:action|category|code|context|decision|domain|event|kind|"
    r"operation|operation_id|outcome|reason|record_id|resource|revision|"
    r"scope|source|status|type|tenant_id|actor_id)$"
)
_SAFE_VALUE = re.compile(r"^[a-zA-Z0-9_.:/@-]{1,96}$")
_DANGEROUS = re.compile(
    r"(?i)(?:bearer|password|passphrase|token|secret|api.?key|private.?key|"
    r"authorization|credential|cookie|session|email|phone|address|body|"
    r"brief|document|content|prompt|raw|traceback|stack|payment|wallet|"
    r"ssn|pan|aadhar|aadhaar|account.?number|contact)"
)


def audit_metadata_safe(value: object) -> dict[str, str]:
    """Keep only known, bounded classifier fields; never stringify objects.

    Strictly no recursion: nested dicts/list contents can contain arbitrary
    founder payloads and error messages. Their representation is never logged.
    """
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        return {"metadata": "[redacted]"}
    output: dict[str, str] = {}
    for key, item in list(value.items())[:32]:
        if not isinstance(key, str):
            continue
        if not _SAFE_KEY.fullmatch(key) or _DANGEROUS.search(key):
            continue
        if type(item) in (int, bool) and len(str(item)) <= 96:
            output[key] = str(item)
        elif (isinstance(item, str) and _SAFE_VALUE.fullmatch(item)
              and (item == "bad_credentials" or not _DANGEROUS.search(item))):
            output[key] = item
        else:
            output[key] = "[redacted]"
    return output
