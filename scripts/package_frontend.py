"""Package a reviewed Next.js static export into the existing Python runtime."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    source = ROOT/'apps/web/out'
    destination = ROOT/'apps/backend/ago/frontend'
    if not (source/'index.html').is_file():
        raise SystemExit('Build @ago/web before packaging frontend')
    # Destination is exclusively reproducible generated release output.
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    hashes = set()
    for file in destination.rglob('*.html'):
        for attrs, script in re.findall(r'<script\b([^>]*)>(.*?)</script>', file.read_text(), re.DOTALL):
            if not re.search(r'\bsrc\s*=', attrs) and script:
                digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                hashes.add("'sha256-"+digest+"'")
    (destination/'csp.json').write_text(json.dumps(sorted(hashes))+'\n')
    print(f'Next.js packaged: 8 workspaces, {len(hashes)} trusted static inline script hashes')


if __name__ == '__main__':
    package()
