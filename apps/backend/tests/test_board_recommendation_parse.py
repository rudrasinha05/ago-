"""Board advisory vote parsing: exactly one explicit line in the persisted draft."""
from ago.company_ollama_chain import board_recommendation


def test_one_explicit_line_is_a_vote():
    assert board_recommendation("BOARD_RECOMMENDATION: DENY\nRISKS: scope") == "deny"


def test_board_prompt_asks_for_the_vote_line_first():
    from ago.company_ollama_chain import run_four_role_chain
    import inspect
    source = inspect.getsource(run_four_role_chain)
    assert "Your FIRST line must be exactly one of these two lines" in source


def test_layout_noise_is_ignored_but_not_content():
    assert board_recommendation("  **BOARD_RECOMMENDATION:** approve.") == "approve"
    assert board_recommendation("BOARD_RECOMMENDATION: APPROVE WITH CHANGES") == "unverified"


def test_missing_or_ambiguous_votes_stay_unverified():
    assert board_recommendation("DECISION: APPROVE\nDELIVERABLE: plan") == "unverified"
    assert board_recommendation(
        "BOARD_RECOMMENDATION: APPROVE\nBOARD_RECOMMENDATION: DENY") == "unverified"
    assert board_recommendation(
        "BOARD_RECOMMENDATION: APPROVE\nBOARD_RECOMMENDATION: APPROVE") == "unverified"
    assert board_recommendation("") == "unverified"


def test_board_roles_get_the_vote_as_their_first_heading_and_others_do_not():
    """Live qwen2.5-coder:1.5b followed the heading list and wrote "DECISION: ..."
    instead of a vote; Board roles now get BOARD_RECOMMENDATION as a heading."""
    from test_local_company_ollama_chain import ApprovedProjectDb
    from ago.company_ollama_chain import run_four_role_chain
    from ago.company_ollama_chain_queries import CompanyOllamaChainQueries

    class Recorder:
        def __init__(self):
            self.prompts = []

        def generate(self, prompt):
            self.prompts.append(prompt)
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: draft"

    db = ApprovedProjectDb()
    participants = CompanyOllamaChainQueries(db).assignments(
        tenant_id=db.tenant, actor_id=db.founder, task=db.task())
    model = Recorder()
    run_four_role_chain(task=db.task(), participants=participants, provider=model)
    board = [p for p in model.prompts if "BOARD_ADVISORY:" in p]
    others = [p for p in model.prompts if "BOARD_ADVISORY:" not in p]
    assert board and others
    assert all("first the single vote line described below, then headings: "
               "DELIVERABLE, RISKS, ACCEPTANCE" in p for p in board)
    assert all("headings: DECISION," not in p for p in board)
    assert all("headings: DECISION, DELIVERABLE, RISKS, ACCEPTANCE" in p for p in others)


def test_heading_form_from_live_qwen_3b_is_one_vote():
    # Exact shape returned by qwen2.5:3b for the CTO seat on the Founder PC.
    live = ("### BOARD_RECOMMENDATION\nDENY\n\n### DELIVERABLE\nThe deliverable for "
            "the AdmissionFlow project will be a complete product blueprint.")
    assert board_recommendation(live) == "deny"
    # CEO shape: an inline vote plus an empty heading followed by other content.
    ceo = ("BOARD_RECOMMENDATION: APPROVE\n\n### BOARD_RECOMMENDATION\n\n"
           "### DELIVERABLE\n\nThe deliverable ...")
    assert board_recommendation(ceo) == "approve"


def test_heading_form_still_needs_exactly_one_clear_vote():
    assert board_recommendation("## BOARD_RECOMMENDATION\nMaybe approve") == "unverified"
    assert board_recommendation(
        "BOARD_RECOMMENDATION: APPROVE\n### BOARD_RECOMMENDATION\nDENY") == "unverified"
    assert board_recommendation("BOARD_RECOMMENDATIONS: APPROVE") == "unverified"
    assert board_recommendation("### BOARD_RECOMMENDATION") == "unverified"


def _chain(answers, overridden=frozenset()):
    """A full five-seat Board + PM + worker with distinct AI employees."""
    from types import SimpleNamespace
    from uuid import uuid4
    from ago.company_ollama_chain import FULL_BOARD_STAGES, run_four_role_chain

    class Scripted:
        def __init__(self):
            self.calls = 0

        def generate(self, prompt):
            self.calls += 1
            return answers[min(self.calls, len(answers)) - 1]

    participants = [{"role": role, "employee_id": str(uuid4()), "employee_name": role.upper()}
                    for role, _, _ in FULL_BOARD_STAGES]
    task = SimpleNamespace(id=str(uuid4()), action="internal:brief", project_context={
        "intake_id": str(uuid4()), "title": "AdmissionFlow", "brief": "Admissions tracker"})
    return run_four_role_chain(task=task, participants=participants, provider=Scripted(),
                               overridden_seats=overridden)


APPROVE = "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: plan"
FIN_DENY = "BOARD_RECOMMENDATION: DENY\nDENY_REASON: No cost estimate for the pilot.\nRISKS: budget"


def test_finance_denial_after_ceo_and_cto_approve_is_offered_to_the_founder():
    result = _chain([APPROVE, APPROVE, FIN_DENY])
    assert result["board_blocked"] is True
    assert result["blocked_by_board_seat"] == "Finance & Budget"
    assert result["founder_override_available"] is True
    finance = result["board_recommendations"][2]
    assert finance["denial_reason"] == "No cost estimate for the pilot."
    assert finance["founder_override"] is False


def test_a_founder_allowed_seat_is_advice_and_the_team_continues():
    result = _chain([APPROVE, APPROVE, FIN_DENY, APPROVE, APPROVE, "DECISION: x", "DECISION: y"],
                    overridden=frozenset({"Finance & Budget"}))
    assert result["board_blocked"] is False
    assert result["founder_overrides_applied"] == ["Finance & Budget"]
    assert result["board_recommendations"][2]["founder_override"] is True
    assert result["board_review_cleared"] is False  # a DENY is never a clean Board pass
    assert result["roles_completed"] == result["roles_expected"]


def test_ceo_or_cto_denials_are_never_overridden():
    cto_deny = _chain([APPROVE, FIN_DENY], overridden=frozenset({"Finance & Budget"}))
    assert cto_deny["blocked_by_board_seat"] == "Technology Oversight"
    assert cto_deny["founder_override_available"] is False
    # An allowed Finance seat still blocks when the CTO did not approve first.
    unclear_cto = _chain([APPROVE, "no vote", FIN_DENY], overridden=frozenset({"Finance & Budget"}))
    assert unclear_cto["blocked_by_board_seat"] == "Technology Oversight"


def test_denial_reason_needs_exactly_one_line():
    from ago.company_ollama_chain import denial_reason
    assert denial_reason("DENY_REASON: a\nDENY_REASON: b") == ""
    assert denial_reason("**DENY_REASON:** budget unknown") == "budget unknown"
    assert denial_reason("BOARD_RECOMMENDATION: DENY") == ""
