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
