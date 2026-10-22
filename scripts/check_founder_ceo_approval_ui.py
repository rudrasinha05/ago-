"""Fail-closed UI/operational regression check for the AGO Founder / CEO contract.

Historical immutable SQL migrations and archival documentation remain untouched.
No independent human reviewer may reappear as a current approval instruction.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "apps" / "web"
BACKEND = ROOT / "apps" / "backend" / "ago" / "company_chat.py"

FORBIDDEN = (
    "independent active human reviewer",
    "active independent human reviewer",
    "pending_independent_review",
    "independent reviewer with approval",
    "third-party reviewer approval",
    "request approval from a reviewer",
    "awaiting another human reviewer",
)


def inspect() -> list[str]:
    failures = []
    for path in sorted(UI.rglob("*")):
        if path.suffix not in {".jsx", ".js", ".tsx", ".ts"} or not path.is_file():
            continue
        text = path.read_text(encoding="utf-8").lower()
        for term in FORBIDDEN:
            if term in text:
                failures.append(f"{path.relative_to(ROOT)}: {term}")
    policy = BACKEND.read_text(encoding="utf-8")
    if "pending_independent_review" in policy:
        failures.append("company_chat: legacy reviewer fallback still active")
    if "approve_ceo_project_stage" not in policy or "approve_ceo_project_task" not in policy:
        failures.append("company_chat: CEO project-scoped task/staffing gate absent")
    if "'pending_founder_decision'" not in policy:
        failures.append("company_chat: Founder-owned staffing decision not exposed")
    return failures


if __name__ == "__main__":
    problems = inspect()
    if problems:
        raise SystemExit("Approval UI contract FAILED:\n" + "\n".join(problems))
    print("PASS: no third-party human approval prompt or stale operational reviewer fallback")
