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
