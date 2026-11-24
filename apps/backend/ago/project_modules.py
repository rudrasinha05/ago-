"""PROJ-014 / PROJ-016: prototype + integration delivery of a project.

Order (Founder, 2026-11-25): requirement analysis -> architecture and module
planning -> Founder approval -> working prototype -> individual module
development -> module testing and QA -> module integration -> complete
regression testing -> final product verification.

This module holds the pure rules: how a module plan is read from the Founder's
brief (or the approved architecture), what each unit asks the AI engineer for,
and how a unit's files join the project's integrated source. Integration never
overwrites: a module adds NEW files on top of the prototype and earlier
modules, and every earlier test runs again with it.
"""
from __future__ import annotations

import ast
import hashlib
import json
import re

MAX_MODULES = 30
# Module rows: "M01<TAB>Institute Setup<TAB>Institute name, ..." or with |, — or :.
_ROW = re.compile(r"(?m)^[ \t>*-]*\b(M\d{2,3})\b[ \t]*(?:[|:—–-][ \t]*)?(.+)$")
_PRIORITY = re.compile(r"(?im)^[^\n]{0,12}\bP([0-3])\b\s*[—–:-]")
_SAFE_PATH = re.compile(r"(?:src/[A-Za-z0-9_./-]+\.py|tests/test_[A-Za-z0-9_./-]+\.py|docs/[A-Za-z0-9_./-]+\.md)")
# Integrated source budget: large enough for a 30-module pilot, small enough
# for one offline Docker run and one database row.
MAX_PROJECT_FILES = 400
MAX_PROJECT_BYTES = 600_000


def _clean(text: str, limit: int) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def _split_row(rest: str) -> tuple[str, str]:
    """(title, what it does) from the text after the module code."""
    for sep in ("\t", " | ", "|", " — ", " – ", " - ", ": "):
        if sep in rest:
            title, _, what = rest.partition(sep)
            if title.strip() and what.strip():
                return _clean(title, 160), _clean(what, 450)
    words = rest.split()
    return _clean(" ".join(words[:3]), 160), _clean(rest, 450)


def extract_modules(text: str) -> dict:
    """Modules named in a brief or an architecture deliverable.

    Returns {"modules": [{"code","title","goal"}], "deferred": [codes]}. When
    the text marks priorities (P0/P1/P2), only the first priority found is
    planned now and the rest are listed as deferred; otherwise every module is
    planned. Duplicates keep their first row. Nothing is invented: a text
    without module rows returns no modules.
    """
    text = str(text or "")
    # An architect's one-line "MODULES: M01 A - x; M02 B - y" becomes one row each.
    text = re.sub(r"(?i)\bMODULES:\s*([^\n]*)",
                  lambda m: "\n" + re.sub(r";\s*(?=M\d{2,3}\b)", "\n", m.group(1)), text)
    marks = [(m.start(), int(m.group(1))) for m in _PRIORITY.finditer(text)]
    rows, seen = [], set()
    for m in _ROW.finditer(text):
        code = m.group(1)
        if code in seen:
            continue
        title, what = _split_row(m.group(2))
        if not title or title.lower().startswith(("module", "id ")):
            continue
        seen.add(code)
        priority = next((p for pos, p in reversed(marks) if pos < m.start()), None)
        rows.append({"code": code, "title": title, "what": what, "priority": priority})
    if not rows:
        return {"modules": [], "deferred": []}
    found = sorted({r["priority"] for r in rows if r["priority"] is not None})
    first = found[0] if found else None
    planned = [r for r in rows if first is None or r["priority"] in (None, first)]
    deferred = [r["code"] for r in rows if r not in planned]
    return {
        "modules": [{"code": r["code"], "title": r["title"],
                     "goal": _clean(r["title"] + ": " + (r["what"] or r["title"]), 600)}
                    for r in planned[:MAX_MODULES]],
        "deferred": deferred + [r["code"] for r in planned[MAX_MODULES:]],
    }


def prototype_goal(title: str) -> str:
    return _clean(
        "Working prototype of " + str(title) + ": the core data model and the main end-to-end "
        "flow that every module will build on, as small Python modules with unittest tests. "
        "Keep it small and correct; the modules come next.", 600)


def unit_slug(code: str, title: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", (code + "_" + title).lower()).strip("_")
    return base[:48].rstrip("_") or code.lower()


def api_summary(files: list[dict], limit: int = 900) -> str:
    """What the integrated code offers, for the next unit's engineer.

    Only names: modules, classes and public functions with their parameters.
    Built by AGO from parsed source (never executed), so it cannot carry
    instructions from earlier model output into the next prompt.
    """
    lines = []
    for f in sorted(files, key=lambda x: x["path"]):
        path = f["path"]
        if not (path.startswith("src/") and path.endswith(".py")):
            continue
        try:
            tree = ast.parse(f["content"])
        except (SyntaxError, ValueError):
            continue
        names = []
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_"):
                names.append(node.name + "(" + ", ".join(a.arg for a in node.args.args) + ")")
            elif isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                methods = [n.name for n in node.body
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                           and not n.name.startswith("_")]
                names.append(node.name + ("[" + ",".join(methods[:6]) + "]" if methods else ""))
        module = path[:-3].replace("/", ".")
        lines.append(module + ": " + (", ".join(names) or "(no public names)"))
    text = "; ".join(lines)
    return text if len(text) <= limit else text[:limit - 3] + "..."


def merge_unit(existing: list[dict], candidate_files: list[dict]) -> list[dict]:
    """The integrated file set after one unit, or ValueError.

    A unit may only ADD files. Changing a file that an earlier unit integrated
    could break an earlier module, so it is refused (Founder rule: integrating
    a module must never break old modules).
    """
    have = {f["path"] for f in existing}
    clash = sorted(f["path"] for f in candidate_files if f["path"] in have)
    if clash:
        raise ValueError("A module may only add new files; it tried to change "
                         + ", ".join(clash)[:200])
    merged = [{"path": f["path"], "content": f["content"]} for f in existing]
    merged += [{"path": f["path"], "content": f["content"]} for f in candidate_files]
    check_project_files(merged)
    return sorted(merged, key=lambda f: f["path"])


def check_project_files(files: list[dict]) -> None:
    if not isinstance(files, list) or not 1 <= len(files) <= MAX_PROJECT_FILES:
        raise ValueError("Project source has too many files")
    seen, total = set(), 0
    for f in files:
        path, content = f.get("path"), f.get("content")
        if not isinstance(path, str) or not isinstance(content, str) or not _SAFE_PATH.fullmatch(path) \
                or ".." in path.split("/"):
            raise ValueError("Unsafe project file path")
        if path in seen:
            raise ValueError("Duplicate project file path")
        seen.add(path)
        total += len(content.encode("utf-8"))
    if total > MAX_PROJECT_BYTES:
        raise ValueError("Project source exceeds its size budget")


def files_sha256(files: list[dict]) -> str:
    canonical = json.dumps(sorted(({"path": f["path"], "content": f["content"]} for f in files),
                                  key=lambda f: f["path"]),
                           sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def test_names(files: list[dict]) -> list[str]:
    names = []
    for f in files:
        if f["path"].startswith("tests/"):
            names += re.findall(r"def (test_[A-Za-z0-9_]+)", f["content"])
    return names
