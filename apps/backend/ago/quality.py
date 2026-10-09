"""M2 independent quality-review gate for proposed work artifacts."""
from dataclasses import dataclass
from enum import Enum


class Verdict(str, Enum):
    PASS = "pass"
    FAIL = "fail"


@dataclass(frozen=True)
class Review:
    tenant_id: str
    artifact_id: str
    author_id: str
    reviewer_id: str
    verdict: Verdict
    evidence: str

    def __post_init__(self):
        if not all((self.tenant_id, self.artifact_id, self.author_id, self.reviewer_id)):
            raise ValueError("Review identity required")
        if self.author_id == self.reviewer_id:
            raise PermissionError("Independent review required")
        if not self.evidence.strip():
            raise ValueError("Review evidence required")

    def assert_accepted(self, *, tenant_id: str, artifact_id: str) -> None:
        if tenant_id != self.tenant_id or artifact_id != self.artifact_id or self.verdict != Verdict.PASS:
            raise PermissionError("Independent QA acceptance required")
