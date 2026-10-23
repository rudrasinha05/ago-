"""Static fail-closed check: strategic Founder vs independent technical review.

Founder project scope is authorized once; the appointed CEO reconciles only
recorded in-scope project tasks. Ordinary governance and independent QA require
authenticated human review, not a model, fake token or second Founder approval.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "components"
BACKEND = ROOT / "apps" / "backend" / "ago"


def inspect() -> list[str]:
    failures = []
    approvals = (WEB / "company-approvals.jsx").read_text(encoding="utf-8")
    founder_action = (WEB / "company-founder-decision.js").read_text(encoding="utf-8")
    badge = (WEB / "company-approval-badge.jsx").read_text(encoding="utf-8")
    company = (BACKEND / "company_chat.py").read_text(encoding="utf-8")
    gate = (BACKEND / "governed_execution.py").read_text(encoding="utf-8")
    governance = (BACKEND / "governance.py").read_text(encoding="utf-8")
    reviewer = (BACKEND / "provision.py").read_text(encoding="utf-8")

    controls = {
        "strategic Founder identity gate":
            'approval:founder' in gate and 'if strategic:' in gate,
        "independent human operational permission":
            'approval:decide' in gate and
            'Active independent reviewer permission required' in governance,
        "stored exact stage scope":
            'founder_project_stage' in governance,
        "independent role provision with independent QA":
            '"approval:decide"' in reviewer and '"qa:review"' in reviewer,
        "conditional Founder inbox routing":
            'a.requires_founder_decision' in approvals and
            'a.requester_id!==me.id' in approvals and
            'approval:decide' in approvals,
        "Founder one-time project handoff":
            'decideFounderScope(api,selected,approve,reason)' in approvals and
            '/ceo/reconcile' in founder_action,
        "human-only employee notification approval":
            'founder&&a.requires_founder_decision' in badge,
        "bounded CEO verification":
            'approve_ceo_project_stage' in company and
            'approve_ceo_project_task' in company,
        "nonfictional stage proposal authorization":
            "'pending_founder_decision'" in company,
    }
    for label, passed in controls.items():
        if not passed:
            failures.append("Missing secure authority boundary: " + label)
    return failures


if __name__ == "__main__":
    problems = inspect()
    if problems:
        raise SystemExit("Approval UI contract FAILED:\n" + "\n".join(problems))
    print("PASS: Founder strategy, independent operational/QA review, bounded CEO work")
