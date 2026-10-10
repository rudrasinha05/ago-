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
