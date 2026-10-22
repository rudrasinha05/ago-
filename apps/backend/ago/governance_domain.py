"""Pure organizational domain values and invariants; no database or framework."""

from dataclasses import dataclass
from enum import Enum

from ago.approvals import ApprovalRequest

# These principles cannot be amended through an API, DNA, a prompt or a tool.
CONSTITUTION_LAWS = {
    "human_authority": "Authenticated human leadership retains final constitutional authority.",
    "legality": "Uncertain legal or contractual authority escalates to humans.",
    "audit": "Material actions preserve actor, evidence, correlation and outcome records.",
    "least_privilege": "No AI may grant itself permissions, budget, autonomy or tool access.",
    "owner_authority": "Founder approves project scope once; only scoped audited CEO verification can authorize routine approved-project tasks.",
    "bounded_autonomy": "Delegated authority is explicit, scoped, monitored and revocable.",
    "data_stewardship": "Private data sharing requires classification, authority and provenance.",
    "transparency": "Material failures, uncertainty, risk and cost remain visible to governance.",
    "safe_evolution": "Changes require evidence, review, bounded rollout and rollback.",
    "advisory_twin": "Simulation and Meta Brain cannot directly apply operational changes.",
    "supremacy": "DNA, strategy, marketplace and optimization cannot override these laws.",
    "emergency": "Emergencies restrict authority temporarily; they never remove audit or human control.",
}
CONSTITUTION_CONTEXTS = (
    "brain", "meta", "organization", "tasks", "agents", "tools", "knowledge",
    "operations", "council", "memory", "insights", "calendar", "messages",
)
CONSTITUTION_REVIEWS = ("legal", "security", "architecture", "audit", "executive")


def constitutional_context(path: str) -> str | None:
    """Classify all business writes; recovery, identity and review stay available."""
    if path.startswith(("/v1/governance/", "/v1/security/", "/v1/sessions", "/v1/console/logout")):
        return None
    parts = path.split("/")
    if len(parts) < 3 or parts[1] != "v1":
        return None
    area = parts[2]
    if area == "console":
        return "tasks"
    return area if area in CONSTITUTION_CONTEXTS else "operations"


def validate_constitution(specification: dict) -> dict:
    """Only operational restrictions change; immutable law and grants never do."""
    import json

    fields = {"title", "rationale", "risk", "affected_rights", "alternatives", "dissent",
              "rollback", "monitoring", "propagation", "blocked_contexts", "simulation_id"}
    if not isinstance(specification, dict) or set(specification) != fields:
        raise ValueError("Complete constitutional evidence package required; laws are immutable")
    for field in fields - {"blocked_contexts", "simulation_id"}:
        value = specification[field]
        if not isinstance(value, str) or not 1 <= len(value.strip()) <= 3000:
            raise ValueError("Substantive constitutional review fields required")
    from uuid import UUID
    UUID(specification["simulation_id"])
    blocked = specification["blocked_contexts"]
    if (not isinstance(blocked, list) or len(blocked) > len(CONSTITUTION_CONTEXTS)
            or any(not isinstance(x,str) or x not in CONSTITUTION_CONTEXTS for x in blocked)
            or len(set(blocked)) != len(blocked)):
        raise ValueError("Explicit unique constitutional business contexts required")
    return json.loads(json.dumps(specification, allow_nan=False))


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
