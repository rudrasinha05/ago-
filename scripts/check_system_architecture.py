"""Read-only Section 1 traceability gate; no database, provider or secret access."""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

from ago.architecture_guard import load_policy, verify

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps/backend/ago"
INVENTORY = ROOT / "docs/architecture/SECTION_01_MODULE_INVENTORY.md"
ROUTERS = {
    "m2_router", "brain_router", "agents_router", "insights_router",
    "operations_router", "knowledge_router", "council_router", "meta_router",
    "tools_router", "console_router",
}
CONTEXTS = {
    "entrypoints", "transport", "governance", "strategy", "workforce",
    "knowledge", "operations", "economics", "platform",
}
LAYERS = {"composition", "transport", "service", "persistence", "domain", "foundation"}


def inventory(policy: dict) -> str:
    rows = [
        "# Section 1 — Complete Source Module Inventory", "",
        "Generated from the Section 14 contract. All imports are checked against source.",
        "Regenerate only after a reviewed policy change; this file grants no permission.", "",
        "| Module | Organizational context | Registered layer | Permitted imports |",
        "|---|---|---|---|",
    ]
    for module, spec in sorted(policy["nodes"].items()):
        link = f"[{module}](../../apps/backend/ago/{module}.py)"
        imports = ", ".join(spec["imports"]) or "None"
        rows.append(f"| {link} | {spec['context']} | {spec['layer']} | {imports} |")
    return "\n".join(rows) + "\n"


def check(root: Path = ROOT) -> list[str]:
    backend = root / "apps/backend/ago"
    policy = load_policy(backend / "architecture_policy.json")
    report = verify(backend, policy)
    errors = [f"module-contract:{v.code}:{v.source}:{v.target}" for v in report.violations]
    nodes = policy["nodes"]
    if {s["context"] for s in nodes.values()} != CONTEXTS:
        errors.append("context-coverage")
    if {s["layer"] for s in nodes.values()} != LAYERS:
        errors.append("layer-coverage")
    tree = ast.parse((backend / "main.py").read_text(encoding="utf-8"))
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and isinstance(n.func, ast.Attribute) and n.func.attr == "include_router"]
    routers = [n.args[0].id for n in calls if n.args and isinstance(n.args[0], ast.Name)]
    if set(routers) != ROUTERS or len(routers) != len(ROUTERS):
        errors.append("router-composition-drift")
    path = root / INVENTORY.relative_to(ROOT)
    if not path.is_file() or path.read_text(encoding="utf-8") != inventory(policy):
        errors.append("module-inventory-drift")
    for document in (
        "docs/architecture/SECTION_01_OVERALL_SYSTEM_ARCHITECTURE.md",
        "docs/architecture/SECTION_14_MODULE_DEPENDENCY_RULES.md",
        "docs/BDR_SECTION_DELIVERY_RULE.md",
    ):
        if not (root / document).is_file():
            errors.append(f"missing-document:{document}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-inventory", action="store_true")
    args = parser.parse_args()
    if args.write_inventory:
        policy = load_policy(BACKEND / "architecture_policy.json")
        if not verify(BACKEND, policy).passed:
            raise ValueError("Cannot regenerate inventory from a failed module contract")
        INVENTORY.write_text(inventory(policy), encoding="utf-8")
    errors = check()
    print(json.dumps({"section": 1, "passed": not errors, "violations": errors}))
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
