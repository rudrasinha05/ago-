"""Section 4 workspace/service ownership and filesystem/package dependency guard."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = Path('docs/architecture/section04_monorepo.json')
IMPORT = re.compile(r'''(?:\bfrom\s*|\bimport\s*\(|\brequire\s*\(|\bimport\s*)["']([^"']+)["']''')


def check(root: Path = ROOT) -> list[str]:
    contract = json.loads((root / CONTRACT).read_text())
    package = json.loads((root / 'package.json').read_text())
    errors = []
    if contract.get('version') != 1 or package.get('private') is not True:
        errors.append('root-contract')
    entries = contract['packages']
    if set(package.get('workspaces', [])) != {v['path'] for v in entries.values()}:
        errors.append('workspace-roster')
    for directory in contract['required_directories']:
        if not (root / directory).is_dir():
            errors.append(f'missing-directory:{directory}')
    for name, entry in entries.items():
        folder = root / entry['path']
        file = folder / 'package.json'
        if not file.is_file():
            errors.append(f'missing-package:{name}')
            continue
        data = json.loads(file.read_text())
        if data.get('name') != name or data.get('private') is not True:
            errors.append(f'package-identity:{name}')
        dependencies = data.get('dependencies', {}) | data.get('peerDependencies', {})
        if {n for n in dependencies if n.startswith('@ago/')} != set(entry['allowed']):
            errors.append(f'package-dependencies:{name}')
        for source in folder.rglob('*'):
            if (source.suffix not in {'.js', '.jsx', '.mjs', '.ts', '.tsx'}
                    or any(p in {'.next', 'node_modules', 'out'} for p in source.parts)):
                continue
            for target in IMPORT.findall(source.read_text()):
                if target.startswith('@ago/'):
                    target_package = '/'.join(target.split('/')[:2])
                    if target_package not in entry['allowed']:
                        errors.append(f'forbidden-package-import:{name}:{target}')
                elif target.startswith('.'):
                    resolved = (source.parent / target).resolve()
                    if not resolved.is_relative_to(folder.resolve()):
                        errors.append(f'filesystem-package-escape:{name}:{target}')
    policy = json.loads((root / 'apps/backend/ago/architecture_policy.json').read_text())
    for name, modules in contract['services'].items():
        file = root / 'services' / name / 'boundary.json'
        if not file.is_file():
            errors.append(f'missing-service-boundary:{name}')
            continue
        data = json.loads(file.read_text())
        if (data.get('name') != name or data.get('deployment') != 'modular-monolith'
                or data.get('modules') != modules or not set(modules) <= set(policy['nodes'])):
            errors.append(f'service-boundary-drift:{name}')
    lock = root / 'package-lock.json'
    if not lock.is_file():
        errors.append('missing-lockfile')
    else:
        locked = json.loads(lock.read_text()).get('packages', {})
        if locked.get('', {}).get('workspaces') != package['workspaces']:
            errors.append('lock-workspace-drift')
    return sorted(set(errors))


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    errors = check()
    print(json.dumps({'section': 4, 'passed': not errors, 'violations': errors}))
    raise SystemExit(2 if errors else 0)
