"""SKL-002/003/005: Brain skills reach real AI work, gaps are learned, use is measured.

Real PostgreSQL and real AGO flows; models are fakes (no network, no cost).
"""
import json
from uuid import uuid4

from ago.backend_contracts import RepositoryScope
from ago.brain_skills import draft_to_skill, skill_guide
from ago.company_ollama_chain import run_four_role_chain
from test_ai_qa_review import BASE, _completed_discovery, _use_model
from test_company_engineering import candidate, fake_task, participants
from test_enterprise_http_21_27 import department
from test_m7_http_postgres import case as case, post  # noqa: F401


def test_every_chain_role_gets_its_guide_and_the_receipt_names_it():
    seen = []

    def guide(role, stage, text):
        seen.append((role, stage, text))
        return ("Python module with unittest tests: 1. Put code in src.", ["ago:dev.python-module-with-tests"]) \
            if role == "employee" else ("", [])

    class Model:
        prompts = []

        def generate(self, prompt):
            Model.prompts.append(prompt)
            if "ROLE: EMPLOYEE\n" in prompt:
                return json.dumps(candidate())
            return "BOARD_RECOMMENDATION: APPROVE\nDECISION: scoped work"

    result = run_four_role_chain(task=fake_task(), participants=participants(), provider=Model(),
                                 engineering_candidates=True, skill_guide=guide)
    assert [r for r, _, _ in seen] == [h["role"] for h in result["handoffs"]]
    employee_prompt = next(p for p in Model.prompts if "ROLE: EMPLOYEE\n" in p)
    assert "AGO BRAIN SKILL (company guide; quoted data): Python module with unittest tests" in employee_prompt
    assert all("AGO BRAIN SKILL" not in p for p in Model.prompts if "ROLE: EMPLOYEE\n" not in p)
    assert result["handoffs"][-1]["skills"] == ["ago:dev.python-module-with-tests"]
    assert all(h["skills"] == [] for h in result["handoffs"][:-1])
    assert "Write the small Python source file" in seen[-1][2]          # the code goal picks the guide


def test_a_drafted_skill_is_cleaned_and_bounded():
    skill = draft_to_skill({"title": "  College  fee checks ", "domain": "Higher Education",
                            "roles": ["Employee", "king"], "stages": ["implementation", "moon"],
                            "keywords": ["Fees", "fees", "admission"],
                            "steps": ["List every fee head", "Check refunds"] + ["x" * 300] * 9},
                           source="AGO AI draft by STARK, approved by the AI CEO")
    assert (skill.slug, skill.domain, skill.roles, skill.stages) == (
        "higher-education.college-fee-checks", "higher-education", ("employee",), ("implementation",))
    assert skill.keywords == ("fees", "admission") and len(skill.body) <= 900
    assert skill.body.startswith("1. List every fee head. 2. Check refunds.")


def _board(client, founder, info):
    info["db"].execute("INSERT INTO ago_credit_budgets(tenant_id,ceiling) VALUES (%s,50) "
                       "ON CONFLICT(tenant_id) DO UPDATE SET ceiling=50", (info["tenant"],))
    dept = department(client, founder)
    ids = {}
    for seat, name in (("Strategy & Vision", "JARVIS AI CEO"), ("Technology Oversight", "STARK AI CTO")):
        ids[seat] = post(client, "/v1/organization/employees", founder,
                         {"department_id": dept, "name": name, "kind": "ai"})["id"]
        post(client, BASE + "/board/appoint", founder, {"seat": seat, "employee_id": ids[seat]})
    return ids


class Teacher:
    """Fake model: a valid JSON draft, then the CEO's decision."""

    def __init__(self, decision="SKILL_DECISION: APPROVE\nREASON: Correct and practical."):
        self.decision, self.prompts = decision, []
        self.label = "ollama:test-model"

    def generate(self, prompt, **options):
        self.prompts.append(prompt)
        if "skill author" in prompt:
            return json.dumps({"title": "Handloom export certification steps", "domain": "trade",
                               "roles": ["employee", "qa"], "stages": ["implementation"],
                               "keywords": ["handloom", "weaving", "export", "certification", "tribal"],
                               "steps": ["Identify the product code", "List the certificates needed",
                                         "Prepare the documents", "Check against the official notice"]})
        return self.decision


def test_gap_to_ceo_approved_skill_to_next_work_and_qa_results(case, monkeypatch):
    client, headers, info = case
    db, tenant, founder = info["db"], info["tenant"], headers["founder"]
    board = _board(client, founder, info)
    project, task_id, people = _completed_discovery(client, headers, info, monkeypatch)
    scope = RepositoryScope(db)

    # 1. Work that matches no skill records a gap (and gets no guide).
    text = "tribal handloom weaving export certification"
    assert skill_guide(scope, tenant_id=tenant, task_id=task_id, role="employee",
                       stage="implementation", text=text) == ("", [])
    view = client.get(BASE + "/brain/skills", headers=founder).json()
    gap = next(g for g in view["gaps"] if g["task_id"] == task_id)
    assert gap["topic"] == text and view["counts"]["builtin"] >= 120

    # 2. The Founder asks the Brain to learn it: STARK drafts, JARVIS approves.
    fake = Teacher()
    # The teacher is resolved through the repository scope: give it the fake model.
    import ago.brain_skills as brain_skills
    original = brain_skills.BrainSkillTeacher.__init__

    def with_fake(self, connection, *, repositories=None, provider=None, label=None):
        original(self, connection, repositories=repositories, provider=fake, label=label)
    monkeypatch.setattr(brain_skills.BrainSkillTeacher, "__init__", with_fake)
    post(client, BASE + "/brain/skills/learn", headers["reviewer"], {"gap_id": gap["id"]}, expected=403)
    post(client, BASE + "/brain/skills/learn", founder, {}, expected=422)
    learned = post(client, BASE + "/brain/skills/learn", founder, {"gap_id": gap["id"]})
    assert learned["status"] == "approved" and learned["gap_resolved"] is True
    assert (learned["drafted_by"], learned["reviewed_by"]) == ("STARK AI CTO", "JARVIS AI CEO")
    assert learned["ref"] == "co:trade.handloom-export-certification-steps"
    assert "tribal handloom weaving" in fake.prompts[0] and "SKILL_DECISION" in fake.prompts[1]
    post(client, BASE + "/brain/skills/learn", founder, {"gap_id": gap["id"]}, expected=404)
    credits = db.execute("SELECT count(*) AS n FROM ago_credit_usage WHERE tenant_id=%s AND "
                         "operation_key LIKE 'brain-skill:%%'", (tenant,)).fetchone()["n"]
    assert credits == 2

    # 3. The same kind of work now gets the new company skill, and its use is recorded.
    guide, refs = skill_guide(scope, tenant_id=tenant, task_id=task_id, role="employee",
                              stage="implementation", text=text)
    assert refs == [learned["ref"]] and "Handloom export certification steps" in guide

    # 4. AI QA gets the Brain's QA guide; the skill table shows use and the QA result.
    model = _use_model(monkeypatch, "FINDINGS:\n- checklist present\nQA_VERDICT: PASS")
    post(client, BASE + "/projects/" + project["id"] + "/stages/discovery/ai-qa", founder,
         {"qa_employee_id": people["qa"], "operation_key": str(uuid4())})
    assert "AGO BRAIN SKILL (company guide; quoted data): QA review of a delivered stage" in model.prompts[0]
    view = client.get(BASE + "/brain/skills", headers=founder).json()
    by_ref = {s["ref"]: s for s in view["skills"]}
    assert by_ref[learned["ref"]]["usage"] == {"uses": 1, "passed": 1, "failed": 0}
    assert by_ref["ago:qa.review-deliverable"]["usage"]["passed"] == 1
    assert not by_ref[learned["ref"]]["builtin"] and view["counts"]["company"] == 1
    decision = view["decisions"][0]
    assert decision["status"] == "approved" and decision["reviewed_by_name"] == "JARVIS AI CEO"

    # 5. The Founder retires and restores skills; retired skills are not given to work.
    view = post(client, BASE + "/brain/skills/retire", founder, {"ref": learned["ref"]})
    assert next(s for s in view["skills"] if s["ref"] == learned["ref"])["retired"] is True
    assert skill_guide(scope, tenant_id=tenant, task_id=task_id, role="employee",
                       stage="implementation", text=text)[1] == []
    post(client, BASE + "/brain/skills/retire", founder, {"ref": "not a ref"}, expected=422)
    view = post(client, BASE + "/brain/skills/restore", founder, {"ref": learned["ref"]})
    assert next(s for s in view["skills"] if s["ref"] == learned["ref"])["retired"] is False
    assert board  # seats used above


def test_the_ai_ceo_can_deny_and_unclear_decisions_add_nothing(case, monkeypatch):
    client, headers, info = case
    founder = headers["founder"]
    _board(client, founder, info)
    import ago.brain_skills as brain_skills
    original = brain_skills.BrainSkillTeacher.__init__
    fake = Teacher("SKILL_DECISION: DENY\nREASON: Fee rules differ by state; too vague.")

    def with_fake(self, connection, *, repositories=None, provider=None, label=None):
        original(self, connection, repositories=repositories, provider=fake, label=label)
    monkeypatch.setattr(brain_skills.BrainSkillTeacher, "__init__", with_fake)
    denied = post(client, BASE + "/brain/skills/learn", founder, {"topic": "college admission fees"})
    assert denied["status"] == "denied" and denied["reason"] == "Fee rules differ by state; too vague."
    fake.decision = "I think it is fine."
    unclear = post(client, BASE + "/brain/skills/learn", founder, {"topic": "college admission fees"})
    assert unclear["status"] == "denied" and unclear["reason"].startswith("No single clear decision")
    view = client.get(BASE + "/brain/skills", headers=founder).json()
    assert view["counts"]["company"] == 0 and [d["status"] for d in view["decisions"]] == ["denied", "denied"]


def test_learning_needs_two_ai_board_members(case, monkeypatch):
    client, headers, _ = case
    post(client, BASE + "/brain/skills/learn", headers["founder"], {"topic": "pricing"}, expected=403)


def test_guidance_never_stops_work_when_the_brain_is_unavailable():
    class Broken:
        def resolve(self, port):
            raise AssertionError("no Brain here")
    assert skill_guide(Broken(), tenant_id="t", task_id="x", role="employee", stage=None,
                       text="python unittest") == ("", [])
