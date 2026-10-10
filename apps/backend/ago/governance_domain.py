"""Pure organizational domain values and invariants; no database or framework."""

from dataclasses import dataclass
from enum import Enum

from ago.approvals import ApprovalRequest


class Risk(str, Enum):
    LOW = "low"
    HIGH = "high"


class Constitution:
    """Conservative policy: unknown actions are high-risk."""

    HIGH_RISK_PREFIXES = (
        "deploy:",
        "spend:",
        "delete:",
        "external:",
        "access:",
        "publish:",
    )

    def classify(self, action: str) -> Risk:
        if not action or not action.strip():
            raise ValueError("Action required")
        # Unknown actions are not automatically safe.
        return Risk.HIGH

    def requires_approval(self, action: str) -> bool:
        return self.classify(action) == Risk.HIGH


@dataclass(frozen=True)
class Decision:
    request: ApprovalRequest


def validate_architecture_change(change_key: str, specification: dict) -> dict:
    import re
    import json

    if not re.fullmatch(r"ARCH-[0-9]{3,8}", change_key):
        raise ValueError("Versioned architecture change identifier required")
    keys = {"sections", "baseline_digest", "candidate_digest", "rationale", "impact",
            "rollback", "evidence_ref"}
    if not isinstance(specification, dict) or set(specification) != keys:
        raise ValueError("Complete architecture impact and rollback record required")
    sections = specification["sections"]
    if (not isinstance(sections, list) or not 1 <= len(sections) <= 34
            or any(type(s) is not int or not 1 <= s <= 34 for s in sections)
            or len(set(sections)) != len(sections)):
        raise ValueError("Explicit unique affected sections required")
    if 29 in sections:
        raise PermissionError("Constitution amendment requires its separate authority")
    for key in ("baseline_digest", "candidate_digest"):
        if not re.fullmatch(r"[0-9a-f]{64}", str(specification[key])):
            raise ValueError("Exact content digests required")
    if specification["baseline_digest"] == specification["candidate_digest"]:
        raise ValueError("Baseline and changed specification must differ")
    for key in ("rationale", "impact", "rollback", "evidence_ref"):
        if not isinstance(specification[key], str) or not 1 <= len(specification[key].strip()) <= 3000:
            raise ValueError("Substantive architecture review fields required")
    return json.loads(json.dumps(specification, allow_nan=False))
