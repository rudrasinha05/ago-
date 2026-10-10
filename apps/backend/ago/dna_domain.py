"""Pure organizational domain values and invariants; no database or framework."""

BASELINE_PROFILE = {
    "qa_target_pct": 85,
    "backlog_limit": 5,
    "budget_alert_pct": 80,
}


def validate_profile(profile: dict) -> dict[str, int]:
    if not isinstance(profile, dict) or set(profile) != set(BASELINE_PROFILE):
        raise ValueError("DNA accepts only the three frozen operating thresholds")
    limits = {
        "qa_target_pct": (50, 100),
        "backlog_limit": (0, 10000),
        "budget_alert_pct": (1, 100),
    }
    for key, (minimum, maximum) in limits.items():
        value = profile[key]
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(f"DNA threshold {key} is out of range")
    return {key: profile[key] for key in BASELINE_PROFILE}


# Descriptive guidance never grants executable permissions or relaxes core controls.
DEFAULT_CHARTER = {
    "mission": "Support the owner with evidence-based, governed organizational work.",
    "vision": "Build a maintainable personal organizational operating system.",
    "values": "Honesty, human authority, privacy, reproducibility and accountability.",
    "leadership_style": "Human direction with clearly delegated responsibility.",
    "engineering_culture": "Freeze scope, finish accepted milestones and use modular code.",
    "research_culture": "Cite sources, retain reproducible evidence and label uncertainty.",
    "decision_philosophy": "Compare alternatives and escalate consequential decisions.",
    "communication_style": "Clear, concise language with actionable explanations.",
    "innovation_philosophy": "Test bounded proposals before independently approved adoption.",
    "risk_appetite": "Conservative; unknown actions retain existing approval requirements.",
    "documentation_philosophy": "Keep source-linked decisions, changes and operating instructions.",
    "security_philosophy": "Least privilege, tenant isolation and immutable audit evidence.",
    "hiring_philosophy": "Assign roles from verified capabilities and human-reviewed needs.",
    "promotion_philosophy": "Use observed outcomes and independent human review.",
    "meeting_philosophy": "Use a purpose, agenda, outcome and responsible owner.",
    "conflict_resolution_philosophy": "Record evidence and escalate unresolved disputes to humans.",
    "learning_philosophy": "Correct errors, preserve provenance and evaluate learning outcomes.",
    "quality_philosophy": "Require independent QA and meaningful regression verification.",
}
OVERRIDABLE_FIELDS = frozenset({
    "communication_style", "documentation_philosophy", "meeting_philosophy", "learning_philosophy",
})
CORE_GUARDS = {
    "human_authority": True, "independent_approval": True,
    "tenant_isolation": True, "audit_required": True, "permission_checks": True,
    "constitution_over_dna": True,
}


def validate_charter(charter: dict, *, override: bool = False) -> dict[str, str]:
    permitted = OVERRIDABLE_FIELDS if override else set(DEFAULT_CHARTER)
    if (not isinstance(charter, dict) or not set(charter) <= permitted
            or (not override and set(charter) != permitted)):
        raise ValueError("Unknown, protected or missing organizational philosophy")
    if any(not isinstance(v, str) or not 1 <= len(v.strip()) <= 2000
           for v in charter.values()):
        raise ValueError("Each philosophy requires 1–2000 characters")
    return {key: value.strip() for key, value in charter.items()}


def inherit_dna(parent: dict, profile: dict, charter: dict) -> dict:
    profile = validate_profile(profile)
    charter = validate_charter(charter, override=True)
    old = parent["profile"]
    if (profile["qa_target_pct"] < old["qa_target_pct"]
            or profile["backlog_limit"] > old["backlog_limit"]
            or profile["budget_alert_pct"] > old["budget_alert_pct"]):
        raise PermissionError("Child DNA cannot weaken parent operating safeguards")
    return {"profile": profile, "charter": {**parent["charter"], **charter}}
