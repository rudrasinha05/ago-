"""Section 6 canonical adapters, private state and route ownership guard."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT):
    errors = []
    mappings = {
        'packages/sdk/session.js':'core.js',
        'packages/ui/compat/views.js':'views.js',
        'packages/ui/compat/actions.js':'actions.js',
        'packages/ui/workspace.css':'styles.css',
    }
    for source, destination in mappings.items():
        actual = (root/source).read_text().replace('"@ago/sdk/session"', '"./core.js"')
        if actual != (root/'apps/backend/ago/console'/destination).read_text():
            errors.append('canonical-adapter-drift:'+destination)
    for folder in ['apps/web/app', 'apps/web/components', 'packages/sdk', 'packages/ui']:
        for path in (root/folder).rglob('*'):
            if path.suffix not in {'.js', '.jsx', '.mjs'}:
                continue
            if any(p in {'tests', 'node_modules', 'out', '.next'} for p in path.parts):
                continue
            source = path.read_text()
            if any(token in source for token in ['localStorage', 'sessionStorage', 'document.cookie', '<iframe']):
                errors.append('private-state-storage-or-frame:'+str(path.relative_to(root)))
    config = (root/'apps/web/next.config.mjs').read_text()
    if "basePath: '/workspace'" not in config or "output: 'export'" not in config:
        errors.append('same-origin-export-contract')
    contract = json.loads((root/'docs/architecture/section06_frontend.json').read_text())
    page = (root/'apps/web/app/[workspace]/page.jsx').read_text()
    for route in contract['workspaces'][1:]:
        if "'"+route+"'" not in page:
            errors.append('missing-route:'+route)
    if contract['session_storage'] != 'tab-memory' or contract['deployment'] != 'modular-monolith-static-export':
        errors.append('deployment-or-session-contract')
    return sorted(set(errors))


if __name__ == '__main__':
    errors = check()
    print(json.dumps({'section':6, 'passed':not errors, 'violations':errors}))
    raise SystemExit(2 if errors else 0)
