"""Section 5 layer, port, constructor-injection and request-contract guard."""

from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from ago.architecture_guard import load_policy, verify

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path("docs/architecture/section05_backend_contracts.json")


def components(root: Path) -> dict:
    found = {}
    for path in sorted((root / "apps/backend/ago").glob("*.py")):
        if path.stem == "backend_contracts":
            continue
        for cls in ast.parse(path.read_text()).body:
            if not isinstance(cls, ast.ClassDef):
                continue
            init = next(
                (
                    m
                    for m in cls.body
                    if isinstance(m, ast.FunctionDef) and m.name == "__init__"
                ),
                None,
            )
            if (
                not init
                or len(init.args.args) < 2
                or init.args.args[1].arg not in {"db", "connection"}
            ):
                continue
            methods = {
                m.name: {
                    "arguments": ast.unparse(m.args),
                    "returns": ast.unparse(m.returns) if m.returns else "Any",
                }
                for m in cls.body
                if isinstance(m, ast.FunctionDef) and not m.name.startswith("_")
            }
            found[cls.name] = {"module": path.stem, "methods": methods}
    return found


def check(root: Path = ROOT) -> list[str]:
    backend = root / "apps/backend/ago"
    contract = json.loads((root / CONTRACT).read_text())
    policy = load_policy(backend / "architecture_policy.json")
    errors = [f"module-boundary:{v.code}" for v in verify(backend, policy).violations]
    actual = components(root)
    if contract.get("version") != 1 or contract.get("components") != actual:
        errors.append("repository-contract-drift")
    ports_tree = ast.parse((backend / "repository_ports.py").read_text())
    ports = {n.name: n for n in ports_tree.body if isinstance(n, ast.ClassDef)}
    binding = next(
        n.value
        for n in ports_tree.body
        if isinstance(n, ast.Assign)
        and any(
            isinstance(t, ast.Name) and t.id == "REPOSITORY_BINDINGS" for t in n.targets
        )
    )
    pairs = {k.id: v.id for k, v in zip(binding.keys, binding.values)}
    if pairs != {n + "Port": "_" + n for n in actual}:
        errors.append("port-binding-drift")
    for name, spec in actual.items():
        port = ports.get(name + "Port")
        if port is None:
            errors.append(f"missing-port:{name}")
            continue
        methods = {n.name: n for n in port.body if isinstance(n, ast.FunctionDef)}
        if set(methods) != set(spec["methods"]):
            errors.append(f"port-method-drift:{name}")
        for method in methods.values():
            if not method.returns or any(
                a.annotation is None
                for a in method.args.args[1:] + method.args.kwonlyargs
            ):
                errors.append(f"untyped-port:{name}:{method.name}")
            expected = spec["methods"].get(method.name)
            if expected:
                args = (
                    ast.parse("def x(" + expected["arguments"] + "): pass").body[0].args
                )
                args = copy.deepcopy(args)
                for arg in args.args[1:] + args.kwonlyargs:
                    if arg.annotation is None:
                        arg.annotation = ast.Name(id="Any", ctx=ast.Load())
                if (
                    ast.unparse(method.args) != ast.unparse(args)
                    or not method.returns
                    or ast.unparse(method.returns) != expected["returns"]
                ):
                    errors.append(f"port-signature-drift:{name}:{method.name}")
        tree = ast.parse((backend / (spec["module"] + ".py")).read_text())
        cls = next(
            n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name
        )
        init = next(
            n
            for n in cls.body
            if isinstance(n, ast.FunctionDef) and n.name == "__init__"
        )
        if (
            not init.args.args[1].annotation
            or ast.unparse(init.args.args[1].annotation) != "DatabaseConnection"
            or not any(
                a.arg == "repositories"
                and a.annotation
                and ast.unparse(a.annotation) == "RepositoryScope | None"
                for a in init.args.kwonlyargs
            )
        ):
            errors.append(f"untyped-injection:{name}")
    for file in backend.glob("*.py"):
        layer = policy["nodes"].get(file.stem, {}).get("layer")
        tree = ast.parse(file.read_text())
        if layer in {"transport", "service", "domain"}:
            for n in ast.walk(tree):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute)
                    and n.func.attr in {"execute", "executemany", "cursor"}
                ):
                    errors.append(f"raw-database-in-layer:{file.stem}")
        if layer != "composition" and file.stem != "backend_contracts":
            for n in ast.walk(tree):
                if (
                    isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Name)
                    and n.func.id in actual
                ):
                    errors.append(f"concrete-construction:{file.stem}:{n.func.id}")
        if layer == "transport" and file.stem != "api_contracts":
            for n in tree.body:
                if isinstance(n, ast.ClassDef) and any(
                    isinstance(b, ast.Name) and b.id == "BaseModel" for b in n.bases
                ):
                    if (file.stem, n.name) != ("auth_api", "LoginResponse"):
                        errors.append(f"permissive-input:{file.stem}:{n.name}")
    return sorted(set(errors))


if __name__ == "__main__":
    errors = check()
    if "repository-contract-drift" in errors:
        expected = json.loads((ROOT / CONTRACT).read_text()).get("components", {})
        observed = components(ROOT)
        drift = {name: {"expected": expected.get(name), "observed": observed.get(name)}
                 for name in sorted(set(expected) | set(observed))
                 if expected.get(name) != observed.get(name)}
        print(json.dumps({"repository_contract_drift_details": drift}, default=str))
    print(json.dumps({"section": 5, "passed": not errors, "violations": errors}))
    raise SystemExit(2 if errors else 0)
