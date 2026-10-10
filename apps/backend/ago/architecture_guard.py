"""Section 14: enforceable AGO modular-monolith dependency contract.

Static checks complement, but do not replace, runtime signed-session RBAC,
independent human review or PostgreSQL governance triggers. No database access.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

MODULE_DIR = Path(__file__).resolve().parent
POLICY_FILE = MODULE_DIR / "architecture_policy.json"
SQL_WRITE = re.compile(
    r"\b(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+"
    r"(?:public\.)?(ago_[a-z][a-z_0-9]*)\b",
    re.IGNORECASE,
)
CONTEXTS = frozenset({
    "entrypoints", "transport", "governance", "strategy", "workforce",
    "knowledge", "operations", "economics", "platform",
})
LAYERS = frozenset({
    "composition", "transport", "service", "persistence", "domain", "foundation",
})
EXCEPTION_KEYS = frozenset({
    "source", "target", "reason", "change_request", "author",
    "reviewed_by", "review_date", "expires_on",
})


@dataclass(frozen=True, order=True)
class Violation:
    code: str
    source: str
    target: str
    detail: str

    def as_dict(self) -> dict[str, str]:
        return {
            "code": self.code, "source": self.source,
            "target": self.target, "detail": self.detail,
        }


@dataclass
class GuardReport:
    modules: int
    edges: set[tuple[str, str]]
    violations: list[Violation]

    @property
    def passed(self) -> bool:
        return not self.violations

    def as_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed, "module_count": self.modules,
            "dependency_count": len(self.edges),
            "violation_count": len(self.violations),
            "violations": [v.as_dict() for v in self.violations],
        }


def load_policy(file: Path = POLICY_FILE) -> dict[str, Any]:
    """Read version-controlled JSON; malformed policy fails closed."""
    with file.open(encoding="utf-8") as handle:
        policy = json.load(handle)
    if not isinstance(policy, dict) or policy.get("schema_version") != 1:
        raise ValueError("Unsupported architecture policy version")
    return policy


def _imports(tree: ast.AST, source: str) -> tuple[set[str], list[Violation]]:
    names: set[str] = set()
    problems: list[Violation] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                if item.name.startswith("ago."):
                    bits = item.name.split(".")
                    if len(bits) != 2:
                        problems.append(Violation(
                            "nested-import", source, item.name,
                            "AGO uses registered root modules; subpackage contract required",
                        ))
                    else:
                        names.add(bits[1])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                if node.level != 1:
                    problems.append(Violation(
                        "relative-import", source, node.module or "",
                        "Root AGO modules may import only from the current package",
                    ))
                elif node.module:
                    names.add(node.module.split(".")[0])
                else:
                    names.update(alias.name for alias in node.names)
                continue
            if node.module == "ago":
                # from ago import <module> — distinguish symbols at validation.
                names.update(alias.name for alias in node.names)
            elif node.module and node.module.startswith("ago."):
                bits = node.module.split(".")
                if len(bits) != 2:
                    problems.append(Violation(
                        "nested-import", source, node.module,
                        "An explicit service-extraction contract is required",
                    ))
                else:
                    names.add(bits[1])
        elif isinstance(node, ast.Call):
            function = node.func
            dynamic = (
                isinstance(function, ast.Name) and function.id == "__import__"
            ) or (
                isinstance(function, ast.Attribute)
                and function.attr == "import_module"
                and isinstance(function.value, ast.Name)
                and function.value.id == "importlib"
            )
            if dynamic:
                if not node.args or not isinstance(node.args[0], ast.Constant):
                    problems.append(Violation(
                        "unreviewable-dynamic-import", source, "",
                        "Dynamic import must use a reviewable literal contract",
                    ))
                elif isinstance(node.args[0].value, str):
                    target = node.args[0].value
                    if target.startswith("ago."):
                        if len(target.split(".")) != 2:
                            problems.append(Violation(
                                "nested-import", source, target,
                                "Nested dynamic AGO module is not registered",
                            ))
                        else:
                            names.add(target.split(".")[1])
    return names, problems


def _cycles(edges: set[tuple[str, str]]) -> list[list[str]]:
    graph: dict[str, set[str]] = {}
    for src, dst in edges:
        graph.setdefault(src, set()).add(dst)
        graph.setdefault(dst, set())
    visiting: set[str] = set()
    visited: set[str] = set()
    stack: list[str] = []
    detected: set[tuple[str, ...]] = set()

    def visit(node: str) -> None:
        if node in visiting:
            index = stack.index(node)
            cycle = stack[index:] + [node]
            ring = cycle[:-1]
            key = min(
                tuple(ring[i:] + ring[:i])
                for i in range(len(ring))
            )
            detected.add(key)
            return
        if node in visited:
            return
        visiting.add(node)
        stack.append(node)
        for neighbor in sorted(graph.get(node, ())):
            visit(neighbor)
        stack.pop()
        visiting.remove(node)
        visited.add(node)

    for name in sorted(graph):
        visit(name)
    return [list(x) + [x[0]] for x in sorted(detected)]


def _exceptions(policy: dict[str, Any], today: dt.date, registered: set[str]) -> tuple[
    dict[tuple[str, str], dict[str, Any]], list[Violation],
]:
    found: dict[tuple[str, str], dict[str, Any]] = {}
    errors: list[Violation] = []
    records = policy.get("exceptions", [])
    if not isinstance(records, list):
        return {}, [Violation(
            "policy-exceptions", "", "", "Exceptions must be an array",
        )]
    for i, record in enumerate(records):
        if not isinstance(record, dict) or set(record) != EXCEPTION_KEYS:
            errors.append(Violation(
                "invalid-exception", f"exception[{i}]", "",
                "Missing or unknown review/expiration fields",
            ))
            continue
        source, target = str(record["source"]), str(record["target"])
        pair = (source, target)
        if (source not in registered or target not in registered
                or source == target or pair in found):
            errors.append(Violation(
                "invalid-exception", source, target,
                "Exception refers to unknown, duplicate or self module",
            ))
            continue
        if not all(isinstance(record[k], str) and record[k].strip()
                   for k in EXCEPTION_KEYS):
            errors.append(Violation(
                "invalid-exception", source, target,
                "Every exception field requires a nonempty value",
            ))
            continue
        if record["reviewed_by"] == record["author"]:
            errors.append(Violation(
                "unreviewed-exception", source, target,
                "The author may not approve their own exception",
            ))
            continue
        if (len(record["reason"].strip()) < 25
                or not re.fullmatch(r"ARCH-[0-9]{3,8}", record["change_request"])):
            errors.append(Violation(
                "unreviewed-exception", source, target,
                "Add a substantive rationale and tracked ARCH change request",
            ))
            continue
        try:
            reviewed = dt.date.fromisoformat(record["review_date"])
            expiration = dt.date.fromisoformat(record["expires_on"])
        except ValueError:
            errors.append(Violation(
                "invalid-exception", source, target, "Invalid ISO review date",
            ))
            continue
        if (reviewed > today or expiration <= today
                or expiration <= reviewed
                or expiration - reviewed > dt.timedelta(days=180)):
            errors.append(Violation(
                "expired-exception", source, target,
                "Exception must be currently valid and last at most 180 days",
            ))
            continue
        found[pair] = record
    return found, errors


def verify(
    source_dir: Path = MODULE_DIR,
    policy: dict[str, Any] | None = None,
    *,
    today: dt.date | None = None,
) -> GuardReport:
    """Detect unregistered files/imports, undocumented edges, layer escapes,
    dynamic imports, cycles and direct writes to protected approval/QA tables.
    """
    if policy is None:
        policy = load_policy()
    today = today or dt.date.today()
    violations: list[Violation] = []
    if policy.get("schema_version") != 1:
        return GuardReport(0, set(), [Violation(
            "policy-version", "", "", "Unsupported schema version",
        )])
    nodes = policy.get("nodes")
    layers = policy.get("layers")
    writers = policy.get("protected_sql_writers")
    if not isinstance(nodes, dict) or not isinstance(layers, dict) or not isinstance(writers, dict):
        return GuardReport(0, set(), [Violation(
            "policy-format", "", "", "Missing module/layer/SQL ownership contracts",
        )])
    source_dir = Path(source_dir)
    actual = {
        p.stem: p for p in sorted(source_dir.glob("*.py"))
    }
    registered = set(nodes)
    for name in sorted(set(actual) - registered):
        violations.append(Violation(
            "unregistered-module", name, "", "Register new module and owner in v1 policy",
        ))
    for name in sorted(registered - set(actual)):
        violations.append(Violation(
            "missing-module", name, "", "Remove stale module entry with review",
        ))
    for src, spec in sorted(nodes.items()):
        if not isinstance(spec, dict) or set(spec) != {
            "context", "layer", "imports",
        }:
            violations.append(Violation(
                "invalid-module-policy", src, "", "Malformed context/layer/imports",
            ))
            continue
        if (spec["context"] not in CONTEXTS or spec["layer"] not in LAYERS
                or not isinstance(spec["imports"], list)
                or len(spec["imports"]) != len(set(spec["imports"]))):
            violations.append(Violation(
                "invalid-module-policy", src, "", "Invalid context or import roster",
            ))
        for target in spec["imports"]:
            if target not in registered or target == src:
                violations.append(Violation(
                    "invalid-approved-edge", src, str(target),
                    "An approved import must refer to another registered module",
                ))
    exceptions, exception_errors = _exceptions(policy, today, registered)
    violations.extend(exception_errors)
    approved_layers = {
        name: set(targets) for name, targets in layers.items()
    }
    if set(approved_layers) != LAYERS or any(
        not targets <= LAYERS for targets in approved_layers.values()
    ):
        violations.append(Violation(
            "invalid-layer-policy", "", "", "Layer direction matrix invalid",
        ))
    edges: set[tuple[str, str]] = set()
    for source, filename in sorted(actual.items()):
        try:
            tree = ast.parse(filename.read_text(encoding="utf-8"), filename=str(filename))
        except (SyntaxError, UnicodeError) as exc:
            violations.append(Violation(
                "invalid-source", source, "", str(exc),
            ))
            continue
        imports, problems = _imports(tree, source)
        violations.extend(problems)
        for target in sorted(imports):
            if target == source:
                violations.append(Violation(
                    "self-import", source, target, "Module imports itself",
                ))
                continue
            if target not in registered:
                violations.append(Violation(
                    "unregistered-import", source, target, "Unknown AGO module",
                ))
                continue
            if source not in registered:
                continue
            edges.add((source, target))
            if (target not in nodes[source].get("imports", [])
                    and (source, target) not in exceptions):
                violations.append(Violation(
                    "forbidden-edge", source, target,
                    "Dependency not on approved baseline or reviewed exception",
                ))
            from_layer = nodes[source]["layer"]
            to_layer = nodes[target]["layer"]
            if to_layer not in approved_layers.get(from_layer, ()):
                violations.append(Violation(
                    "layer-violation", source, target,
                    f"{from_layer} may not depend on {to_layer}",
                ))
        # Only these reviewed repositories can mutate high-impact state.
        # This AST string scan complements DB guards; it is not SQL parsing.
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            for match in SQL_WRITE.finditer(node.value):
                table = match.group(1).lower()
                if table in writers and source not in writers[table]:
                    violations.append(Violation(
                        "protected-sql-write", source, table,
                        "Protected approval/QA state must use owned repositories",
                    ))
    for source, spec in sorted(nodes.items()):
        for target in spec.get("imports", ()):
            if (source, target) not in edges:
                violations.append(Violation(
                    "stale-approved-edge", source, target,
                    "Remove unused dependency from policy after review",
                ))
    for pair in sorted(exceptions):
        if pair not in edges:
            violations.append(Violation(
                "stale-exception", pair[0], pair[1],
                "Unused temporary permission must be deleted",
            ))
    for cycle in _cycles(edges):
        violations.append(Violation(
            "circular-dependency", cycle[0], cycle[-1], " -> ".join(cycle),
        ))
    unique = sorted(set(violations))
    return GuardReport(len(actual), edges, unique)


def to_dot(report: GuardReport, policy: dict[str, Any]) -> str:
    """Deterministic Graphviz DOT for independent architecture review."""
    nodes = policy["nodes"]
    lines = [
        "digraph AGO_Module_Dependencies {",
        '  graph [rankdir="LR", label="AGO Section 14 module dependencies"];',
        '  node [shape="box", style="rounded"];',
    ]
    for name in sorted(nodes):
        spec = nodes[name]
        lines.append(
            f'  "{name}" [label="{name}\\n{spec["context"]} / {spec["layer"]}"];'
        )
    for source, target in sorted(report.edges):
        lines.append(f'  "{source}" -> "{target}";')
    lines.append("}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate frozen AGO Section 14 module dependency contract",
    )
    parser.add_argument("command", choices=("check",))
    parser.add_argument("--dot", type=Path, help="Optional Graphviz artifact path")
    parser.add_argument("--json", action="store_true", help="Machine-readable report")
    args = parser.parse_args(argv)
    try:
        policy = load_policy()
        report = verify(policy=policy)
        if args.dot:
            args.dot.parent.mkdir(parents=True, exist_ok=True)
            args.dot.write_text(to_dot(report, policy), encoding="utf-8")
        if args.json:
            print(json.dumps(report.as_dict(), sort_keys=True))
        else:
            print(
                f"Section 14: {report.modules} modules, "
                f"{len(report.edges)} approved imports, "
                f"{len(report.violations)} violation(s)"
            )
            for issue in report.violations:
                print(
                    f"  {issue.code}: {issue.source} -> {issue.target}: {issue.detail}"
                )
        return 0 if report.passed else 2
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        print(f"Section 14 policy validation failed: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
