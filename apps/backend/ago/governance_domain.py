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
