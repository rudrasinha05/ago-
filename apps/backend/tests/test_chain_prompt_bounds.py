"""Every prompt of every governed stage run fits the local model bound.

Live 2026-11-19 a 4307-character prompt (Board revision + test evidence) failed
the AdmissionFlow quality run as handler_error. This sweeps every stage, every
Board seat denying, rework feedback, revision notes and test evidence with the
LARGEST inputs the database can hold (multi-line), so no combination can stop
a project on prompt length again. No database, no model: a scripted provider.
"""
import itertools

import pytest

from ago.company_ollama_chain import PROMPT_LIMIT, fit_prompt, run_four_role_chain
from test_local_company_ollama_chain import ApprovedProjectDb

STAGES = ("discovery", "architecture", "implementation", "quality", "release")
SEATS = ("ceo", "cto", "finance", "risk", "quality")
LONG = ("line of quoted founder text with detail\n" * 200)


class Scripted:
    """Approves, except one seat that first denies with a maximal reason."""

    def __init__(self, deny_seat):
        self.deny_seat, self.prompts, self.denied = deny_seat, [], False

    def generate(self, prompt, **_):
        self.prompts.append(prompt)
        if "BOARD_ADVISORY:" in prompt or "Board vote" in prompt:
            if (self.deny_seat and not self.denied
                    and "ROLE: " + self.deny_seat.upper() + "\n" in prompt):
                self.denied = True
                return "BOARD_RECOMMENDATION: DENY\nDENY_REASON: " + "budget risk " * 80
            return "BOARD_RECOMMENDATION: APPROVE\nDELIVERABLE: " + "d" * 900
        return "DECISION: " + ("x" * 90 + "\n") * 40


def participants(db):
    return [{"role": r, "employee_id": e, "employee_name": r} for r, e in (
        ("ceo", db.ceo), ("cto", db.cto), ("finance", db.finance), ("risk", db.risk),
        ("quality", db.quality), ("pm", db.pm), ("employee", db.implementer))]


@pytest.mark.parametrize("stage,feedback,revision,evidence,deny_seat", list(itertools.product(
    STAGES, (False, True), (False, True), (False, True), (None,) + SEATS)))
def test_no_combination_exceeds_the_prompt_bound(stage, feedback, revision, evidence, deny_seat):
    db = ApprovedProjectDb()
    task = db.task()
    task.project_context.update({
        "title": "T" * 180, "brief": LONG, "stage": stage, "deliverable": "D" * 400,
        "prior_work": [{"stage": "architecture", "draft": LONG}],
        "recovery_feedback": LONG if feedback else "", "failed_work": LONG if feedback else "",
        "test_evidence": ("AGO TEST EVIDENCE: 9 test(s) EXECUTED ... " + LONG) if evidence else "",
    })
    model = Scripted(deny_seat)
    try:
        run_four_role_chain(task=task, participants=participants(db), provider=model,
                            revision_notes=LONG if revision else "")
    except PermissionError:
        pass            # a recorded Board stop is a governed outcome, not a crash
    assert model.prompts
    assert max(len(p) for p in model.prompts) <= PROMPT_LIMIT


def test_fit_prompt_trims_only_quoted_data_and_keeps_instructions():
    text = ("ROLE: CEO\nRULE: keep me\nFounder project brief (untrusted quoted data): "
            + "b" * 5000 + "\nREMINDER: vote first\n")
    fitted = fit_prompt(text)
    assert len(fitted) <= PROMPT_LIMIT
    assert fitted.startswith("ROLE: CEO\nRULE: keep me\n") and fitted.endswith("REMINDER: vote first\n")
    with pytest.raises(ValueError):
        fit_prompt("instructions only " * 400)
