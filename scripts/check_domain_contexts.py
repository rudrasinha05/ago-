"""Section 3 complete module/context and reviewed SQL-access boundary audit."""
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path

from ago.architecture_guard import load_policy, verify

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path('docs/architecture/section03_domain_contracts.json')
TABLE = re.compile(
    r'\b(?:FROM|JOIN|INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+(?:public\.)?(ago_[a-z0-9_]+)',
    re.IGNORECASE,
)


def sql_access(root: Path) -> dict[str, list[str]]:
    result = {}
    for path in sorted((root / 'apps/backend/ago').glob('*.py')):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        tables = {m.group(1).lower() for node in ast.walk(tree)
                  if isinstance(node, ast.Constant) and isinstance(node.value, str)
                  for m in TABLE.finditer(node.value)}
        result[path.stem] = sorted(tables)
    return result


def check(root: Path = ROOT) -> list[str]:
    policy = load_policy(root / 'apps/backend/ago/architecture_policy.json')
    contract = json.loads((root / CONTRACT).read_text(encoding='utf-8'))
    report = verify(root / 'apps/backend/ago', policy)
    errors = [f'module-boundary:{v.code}' for v in report.violations]
    if contract.get('version') != 1:
        errors.append('contract-version')
    modules = {name: spec['context'] for name, spec in policy['nodes'].items()}
    if contract.get('modules') != modules:
        errors.append('context-module-drift')
    contexts = contract.get('contexts', {})
    if set(contexts) != set(modules.values()):
        errors.append('context-coverage')
    required = {'purpose', 'aggregates', 'value_objects', 'repositories', 'services',
                'invariants', 'published_language', 'consistency'}
    for name, spec in contexts.items():
        if set(spec) != required or not all(spec.values()):
            errors.append(f'incomplete-context:{name}')
    actual = sql_access(root)
    if contract.get('sql_access') != actual:
        errors.append('unreviewed-sql-access')
    return sorted(set(errors))


def main() -> int:
    argparse.ArgumentParser(description=__doc__).parse_args()
    errors = check()
    print(json.dumps({'section': 3, 'passed': not errors, 'violations': errors}))
    return 2 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
