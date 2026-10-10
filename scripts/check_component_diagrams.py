"""Section 2 source-linked component views: deterministic generation and drift checks."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = Path("docs/architecture/section02_components.json")
OUTPUT = Path("docs/architecture/SECTION_02_COMPONENT_VIEWS.md")
REQUIRED = {
    "leadership": {"brain", "meta", "council", "approval"},
    "organization": {"departments", "managers", "employees"},
    "orchestration": {"oos", "scheduler", "workflow", "tasks"},
    "knowledge": {"memory", "graph", "handoffs", "communications"},
    "evidence": {"execution", "qa", "audit", "twin", "dashboard"},
    "deployment": {"api", "security", "postgres", "outbox", "infrastructure"},
}
STATUSES = {"bounded", "partial", "planned"}


def source_exists(root: Path, reference: str) -> bool:
    try:
        path, symbol = reference.split("#")
        if not path.startswith("apps/backend/ago/") or ".." in Path(path).parts:
            return False
        current = ast.parse((root / path).read_text(encoding="utf-8"))
        for part in symbol.split("."):
            current = next(n for n in current.body if isinstance(
                n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef),
            ) and n.name == part)
        return True
    except (ValueError, StopIteration, OSError, SyntaxError, AttributeError):
        return False


def validate(catalog: dict, root: Path = ROOT) -> list[str]:
    errors = []
    if not isinstance(catalog, dict) or catalog.get("version") != 1:
        return ["catalog-version"]
    components, views = catalog.get("components"), catalog.get("views")
    if not isinstance(components, dict) or not isinstance(views, list):
        return ["catalog-format"]
    for name, c in components.items():
        if not re.fullmatch(r"[a-z]+", name) or not isinstance(c, dict):
            errors.append("invalid-component")
            continue
        if (c.get("status") not in STATUSES or not isinstance(c.get("sources"), list)
                or not isinstance(c.get("label"), str)
                or not re.fullmatch(r"[A-Za-z0-9 /—()-]+", c["label"])):
            errors.append(f"invalid-component:{name}")
            continue
        if (c["status"] == "planned") != (not c["sources"]):
            errors.append(f"unsupported-status:{name}")
        for source in c["sources"]:
            if not isinstance(source, str) or not source_exists(root, source):
                errors.append(f"missing-source:{name}")
    ids = [v.get("id") for v in views if isinstance(v, dict)]
    if set(ids) != set(REQUIRED) or len(ids) != len(REQUIRED):
        errors.append("view-coverage")
    used = set()
    for view in views:
        if not isinstance(view, dict) or view.get("id") not in REQUIRED:
            errors.append("invalid-view")
            continue
        key = view["id"]
        nodes = view.get("nodes", [])
        if (not isinstance(nodes, list) or any(not isinstance(n, str) for n in nodes)
                or len(nodes) != len(set(nodes)) or not set(nodes) <= set(components)
                or not REQUIRED[key] <= set(nodes)):
            errors.append(f"node-coverage:{key}")
            continue
        used.update(nodes)
        edges = view.get("edges")
        if not isinstance(edges, list):
            errors.append(f"invalid-edges:{key}")
            continue
        pairs = set()
        for edge in edges:
            if not isinstance(edge, dict):
                errors.append(f"invalid-edge:{key}")
                continue
            a, b = edge.get("from"), edge.get("to")
            if a not in nodes or b not in nodes or a == b or (a, b) in pairs:
                errors.append(f"invalid-edge:{key}")
                continue
            pairs.add((a, b))
            kind, evidence = edge.get("kind"), edge.get("evidence")
            if (kind not in {"current", "proposed"} or not isinstance(evidence, list)
                    or not isinstance(edge.get("label"), str)
                    or not re.fullmatch(r"[A-Za-z0-9 /_-]+", edge["label"])):
                errors.append(f"invalid-edge-contract:{key}")
                continue
            if kind == "current":
                if not evidence or any(components[n]["status"] == "planned" for n in (a, b)):
                    errors.append(f"unsupported-current-edge:{key}")
                for source in evidence:
                    if not isinstance(source, str) or not source_exists(root, source):
                        errors.append(f"missing-edge-evidence:{key}")
            elif evidence:
                errors.append(f"proposed-edge-has-runtime-evidence:{key}")
    if used != set(components):
        errors.append("unused-component")
    return errors


def render(catalog: dict) -> str:
    lines = [
        "# Section 2 — Source-linked High-Level Component Views", "",
        "Generated from `section02_components.json`; check with",
        "`python scripts/check_component_diagrams.py`. Read the companion",
        "`SECTION_02_HIGH_LEVEL_COMPONENT_DIAGRAM.md` for acceptance and boundaries.", "",
        "**Legend:** bounded = existing narrow capability; partial = existing foundation",
        "with broader scope outstanding; planned = absent target subsystem.",
        "Solid arrows describe the labelled current relationship, supported by a",
        "source symbol; dotted arrows describe a proposed interaction, never an",
        "implemented call. Relationships can be queries, references or constraints:",
        "these are not an import graph, deployment sequence or autonomous control loop.", "",
        "## Component catalog", "",
        "| Component | Capability status | Source symbols |", "|---|---|---|",
    ]
    for c in catalog["components"].values():
        refs = "; ".join(f"[{s.split('#')[1]}](../../{s.split('#')[0]})"
                         for s in c["sources"]) or "Future scope; no runtime implementation"
        lines.append(f"| {c['label']} | {c['status']} | {refs} |")
    for view in catalog["views"]:
        lines.extend(["", f"## {view['title']}", "", "```mermaid", "flowchart TD"])
        for node in view["nodes"]:
            c = catalog["components"][node]
            lines.append(f'    c_{node}["{c["label"]} ({c["status"]})"]')
        for e in view["edges"]:
            arrow = "-->" if e["kind"] == "current" else "-.->"
            lines.append(f'    c_{e["from"]} {arrow}|"{e["label"]}"| c_{e["to"]}')
        lines.extend(["```", "", "| Relationship | Meaning | Evidence |", "|---|---|---|"])
        for e in view["edges"]:
            refs = "; ".join(f"[{s.split('#')[1]}](../../{s.split('#')[0]})"
                             for s in e["evidence"]) or "Proposed; not implemented"
            lines.append(f"| {e['from']} → {e['to']} | {e['label']} | {refs} |")
    return "\n".join(lines) + "\n"


def check(root: Path = ROOT) -> list[str]:
    catalog = json.loads((root / CATALOG).read_text(encoding="utf-8"))
    errors = validate(catalog, root)
    if not errors:
        output = root / OUTPUT
        if not output.is_file() or output.read_text(encoding="utf-8") != render(catalog):
            errors.append("component-diagram-drift")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    if args.write:
        catalog = json.loads((ROOT / CATALOG).read_text(encoding="utf-8"))
        errors = validate(catalog)
        if errors:
            print(json.dumps({"passed": False, "violations": errors}))
            return 2
        (ROOT / OUTPUT).write_text(render(catalog), encoding="utf-8")
    errors = check()
    print(json.dumps({"section": 2, "passed": not errors, "violations": errors}))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
