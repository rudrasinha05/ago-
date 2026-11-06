"""Package a reviewed Next.js static export into the existing Python runtime."""
from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def flatten_segment_payloads(root: Path) -> int:
    """Match Next.js's client prefetch names on every OS.

    On Linux the static export writes `strategy/__next.$d$workspace.__PAGE__.txt`,
    which is the exact URL the browser prefetches. Next.js on Windows writes the
    same payload as a folder, `strategy/__next.$d$workspace/__PAGE__.txt`, so every
    prefetch 404ed on the Founder's PC. Rename such files to the dotted name.
    Never overwrites an existing file; a no-op for Linux builds.
    """
    moved = 0
    for folder in sorted(root.rglob('__next.*'), key=lambda p: len(p.parts), reverse=True):
        if not folder.is_dir():
            continue
        for file in sorted(folder.rglob('*')):
            if not file.is_file():
                continue
            relative = file.relative_to(folder).as_posix().replace('/', '.')
            target = folder.parent / (folder.name + '.' + relative)
            if target.exists():
                raise SystemExit(f'Refusing to overwrite Next.js payload {target.name}')
            file.rename(target)
            moved += 1
        shutil.rmtree(folder)
    return moved


def package():
    source = ROOT/'apps/web/out'
    destination = ROOT/'apps/backend/ago/frontend'
    if not (source/'index.html').is_file():
        raise SystemExit('Build @ago/web before packaging frontend')
    # Delete only the retired, repo-owned M9 static bundle. This also clears
    # leftover untracked files from older local installations on Windows.
    retired = ROOT/'apps/backend/ago/console'
    if retired.is_dir():
        shutil.rmtree(retired)
    # Destination is exclusively reproducible generated release output.
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    flattened = flatten_segment_payloads(destination)
    hashes = set()
    for file in destination.rglob('*.html'):
        for attrs, script in re.findall(r'<script\b([^>]*)>(.*?)</script>', file.read_text(), re.DOTALL):
            if not re.search(r'\bsrc\s*=', attrs) and script:
                digest = base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
                hashes.add("'sha256-"+digest+"'")
    (destination/'csp.json').write_text(json.dumps(sorted(hashes))+'\n')
    print(f'Next.js packaged: 8 workspaces, {len(hashes)} trusted static inline script hashes')
    if flattened:
        print(f'Windows Next.js prefetch payloads renamed: {flattened}')


if __name__ == '__main__':
    package()
