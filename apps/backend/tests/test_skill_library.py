"""SKL-001/SKL-002/SKL-004: the built-in Company Brain skill library."""
import pytest

from ago.skill_library import (
    MAX_BODY, Skill, builtin_skills, company_skill, guide_text, parse, select, validate,
)

REQUIRED_DOMAINS = {
    "development", "architecture", "devops", "security", "qa", "data-ai", "design",
    "graphics", "product", "project-management", "business", "marketing", "sales",
    "finance", "legal", "hr", "operations", "research-writing", "politics-policy",
    "education", "communication",
}


def test_every_builtin_skill_is_valid_unique_short_and_sourced():
    skills = builtin_skills()
    assert len(skills) >= 120
    assert len({s.slug for s in skills}) == len(skills)
    assert {s.domain for s in skills} >= REQUIRED_DOMAINS
    for skill in skills:
        assert skill.ref == "ago:" + skill.slug and skill.builtin
        assert 80 <= len(skill.body) <= MAX_BODY
        assert skill.source.startswith("AGO original")       # nothing copied without a license
        assert skill.roles and skill.stages and skill.keywords


@pytest.mark.parametrize("text,role,stage,expected", [
    ("Write the small Python source file and its unittest file for the first capability",
     "employee", "implementation", "dev.python-module-with-tests"),
    ("Review the delivered discovery deliverable against acceptance evidence", "qa", "discovery",
     "qa.review-deliverable"),
    ("Find a market opportunity for an admissions product and estimate demand", "ceo", "discovery",
     "biz.opportunity-finding"),
    ("Design the logo and brand mark for AdmissionFlow", "employee", "implementation", "gfx.logo-brief"),
    ("Analyze the new state education policy and its effect on colleges", "employee", "discovery",
     "pol.policy-analysis"),
    ("Plan the SEO keywords and ranking for the website", "employee", "release", "mkt.seo"),
])
def test_the_right_skill_is_chosen_for_the_work(text, role, stage, expected):
    chosen = select(text, role=role, stage=stage)
    assert chosen and chosen[0].slug == expected
    assert select(text, role=role, stage=stage) == chosen             # deterministic


def test_selection_respects_budget_limit_retired_skills_and_needs_a_real_topic_match():
    text = "python unittest test module src package code"
    assert sum(len(s.body) + len(s.title) + 4 for s in select(text, budget=700, limit=5)) <= 700
    assert len(select(text, limit=1)) == 1
    first = select(text)[0]
    assert first.ref not in {s.ref for s in select(text, retired=frozenset({first.ref}))}
    assert select("hello there", role="employee", stage="implementation") == []   # role alone is not a match
    assert "Python module with unittest tests:" in guide_text(select(text, limit=1))


def test_company_skills_join_selection_and_are_validated():
    row = {"slug": "admissions.fees", "title": "College fee structure checks", "domain": "education",
           "roles": ["employee"], "stages": ["implementation"], "keywords": ["fees", "admission", "college"],
           "source": "AGO AI draft approved by AI CEO", "body": "1. List every fee head. " * 4}
    skill = company_skill(row)
    assert skill.ref == "co:admissions.fees" and not skill.builtin
    assert select("college admission fees rules", extra=(skill,))[0].ref == "co:admissions.fees"
    for bad in ({**row, "slug": "Bad Slug"}, {**row, "body": "short"}, {**row, "roles": ["king"]},
                {**row, "source": ""}, {**row, "keywords": []}):
        with pytest.raises(ValueError):
            company_skill(bad)


def test_parser_reads_the_file_format():
    text = ("# Title\n\n## x.one\ntitle: One skill\nroles: employee\nstages: discovery\n"
            "keywords: alpha, beta\nsource: AGO original (test)\n---\n" + "Do the thing well. " * 6)
    (skill,) = parse(text, "testing")
    assert (skill.slug, skill.domain, skill.roles, skill.keywords) == ("x.one", "testing", ("employee",), ("alpha", "beta"))
    with pytest.raises(ValueError):
        validate(Skill(ref="ago:x", slug="x", title="Ok title", domain="d", roles=("employee",),
                       stages=("discovery",), keywords=("k",), source="", body="b" * 100))
