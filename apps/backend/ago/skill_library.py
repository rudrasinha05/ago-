"""Company Brain skill library (SKL-001, SKL-002, SKL-004).

A skill is a short, sourced "how to do it" guide. Built-in skills ship as
Markdown files in ``ago/skills``; a company's own approved skills come from
its database and are passed in. Selection is deterministic keyword, role and
stage matching, so the same task always gets the same guide. Skills are
guidance text only: they never grant a permission, a tool or an approval.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

SKILL_DIR = Path(__file__).with_name("skills")
MAX_BODY = 900
ROLES = ("ceo", "cto", "finance", "risk", "quality", "pm", "employee", "qa", "chat")
STAGES = ("discovery", "architecture", "implementation", "quality", "release")
_SLUG = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)*")
_WORD = re.compile(r"[a-z0-9][a-z0-9+#.-]*")
_STOP = frozenset(
    "a an and are as at be by for from has have how i in into is it its of on or our "
    "that the their this to was we what when which will with you your stage work "
    "project draft role goal approved internal task founder company ago".split())


@dataclass(frozen=True)
class Skill:
    ref: str            # "ago:<slug>" for built-in, "co:<slug>" for a company skill
    slug: str
    title: str
    domain: str
    roles: tuple[str, ...]
    stages: tuple[str, ...]
    keywords: tuple[str, ...]
    source: str
    body: str
    builtin: bool = True
    extra: dict = field(default_factory=dict, compare=False, hash=False)

    def public(self) -> dict:
        return {"ref": self.ref, "slug": self.slug, "title": self.title, "domain": self.domain,
                "roles": list(self.roles), "stages": list(self.stages),
                "keywords": list(self.keywords), "source": self.source, "body": self.body,
                "builtin": self.builtin, **self.extra}


def _list(value: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(v.strip().lower() for v in value.split(",") if v.strip()))


def validate(skill: Skill) -> Skill:
    """Refuse a skill AGO could not use safely or fairly."""
    if not _SLUG.fullmatch(skill.slug) or len(skill.slug) > 80:
        raise ValueError("Skill slug: lowercase letters, digits, dots and dashes")
    if not 3 <= len(skill.title) <= 120:
        raise ValueError("Skill title must be 3 to 120 characters")
    if not _SLUG.fullmatch(skill.domain):
        raise ValueError("Skill domain must be a simple name")
    if not skill.keywords or len(skill.keywords) > 30:
        raise ValueError("A skill needs 1 to 30 keywords")
    if set(skill.roles) - set(ROLES) or set(skill.stages) - set(STAGES):
        raise ValueError("Unknown role or stage in a skill")
    if not 3 <= len(skill.source) <= 200:
        raise ValueError("Every skill names its source")
    if not 80 <= len(skill.body) <= MAX_BODY:
        raise ValueError("Skill text must be 80 to %d characters" % MAX_BODY)
    return skill


def parse(text: str, domain: str) -> list[Skill]:
    """Skills in one Markdown file: '## slug', 'key: value' lines, '---', body."""
    skills = []
    for chunk in re.split(r"(?m)^## ", text)[1:]:
        head, _, body = chunk.partition("\n---\n")
        lines = head.strip().splitlines()
        slug = lines[0].strip()
        meta = {}
        for line in lines[1:]:
            key, _, value = line.partition(":")
            meta[key.strip().lower()] = value.strip()
        skills.append(validate(Skill(
            ref="ago:" + slug, slug=slug, title=meta.get("title", ""), domain=domain,
            roles=_list(meta.get("roles", "")), stages=_list(meta.get("stages", "")),
            keywords=_list(meta.get("keywords", "")), source=meta.get("source", ""),
            body=body.strip())))
    return skills


@lru_cache(maxsize=1)
def builtin_skills() -> tuple[Skill, ...]:
    found: dict[str, Skill] = {}
    for path in sorted(SKILL_DIR.glob("*.md")):
        for skill in parse(path.read_text(encoding="utf-8"), path.stem):
            if skill.slug in found:
                raise ValueError("Duplicate skill " + skill.slug)
            found[skill.slug] = skill
    return tuple(found.values())


def company_skill(row: dict) -> Skill:
    """A company's approved skill from its database row."""
    return validate(Skill(
        ref="co:" + str(row["slug"]), slug=str(row["slug"]), title=str(row["title"]),
        domain=str(row["domain"]), roles=tuple(row.get("roles") or ()),
        stages=tuple(row.get("stages") or ()), keywords=tuple(row.get("keywords") or ()),
        source=str(row["source"]), body=str(row["body"]), builtin=False))


def _words(text: str) -> set[str]:
    return {w.strip(".-") for w in _WORD.findall(text.lower())} - _STOP


def score(skill: Skill, words: set[str], role: str | None, stage: str | None) -> int:
    """Topic match first; role and stage only break ties between matching skills."""
    keywords = set()
    for k in skill.keywords:
        keywords |= _words(k)
    topic = 3 * len(words & keywords) + len(words & _words(skill.title))
    # One shared word is chance ("refund" in a fee rule is not customer support).
    if topic < 4:
        return 0
    return topic + (2 if role and role in skill.roles else 0) + (2 if stage and stage in skill.stages else 0)


# A guide needs two topic hits (a keyword and a title word, or two keywords).
MIN_SCORE = 5


def select(text: str, *, role: str | None = None, stage: str | None = None,
           extra: tuple[Skill, ...] = (), retired: frozenset[str] = frozenset(),
           limit: int = 2, budget: int = 900) -> list[Skill]:
    """The best skills for this work, inside a character budget."""
    words = _words(text)
    ranked = sorted(
        ((score(s, words, role, stage), s) for s in (*builtin_skills(), *extra) if s.ref not in retired),
        key=lambda pair: (-pair[0], pair[1].ref))
    chosen, used = [], 0
    for value, skill in ranked:
        if value < MIN_SCORE or len(chosen) >= limit:
            break
        if used + len(skill.body) + len(skill.title) + 4 > budget:
            continue
        chosen.append(skill)
        used += len(skill.body) + len(skill.title) + 4
    return chosen


def guide_text(skills: list[Skill]) -> str:
    """The prompt section text for the chosen skills."""
    return " | ".join(s.title + ": " + " ".join(s.body.split()) for s in skills)
