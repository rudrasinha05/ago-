"""Check the packager's Windows Next.js prefetch-name fix: python scripts/test_package_frontend.py"""
import importlib.util
import tempfile
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'package_frontend', Path(__file__).with_name('package_frontend.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def build(root: Path, files: dict[str, str]):
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')


def names(root: Path):
    return sorted(p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file())


with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    # Layout Next.js writes on Windows (observed on the Founder's PC).
    build(root, {
        'strategy/__next.$d$workspace/__PAGE__.txt': 'strategy page',
        'strategy/__next._tree.txt': 'tree',
        '_not-found/__next._not-found/__PAGE__.txt': 'missing page',
        'strategy/index.html': '<html></html>',
    })
    assert module.flatten_segment_payloads(root) == 2
    assert names(root) == [
        '_not-found/__next._not-found.__PAGE__.txt',
        'strategy/__next.$d$workspace.__PAGE__.txt',
        'strategy/__next._tree.txt',
        'strategy/index.html',
    ], names(root)
    assert (root / 'strategy/__next.$d$workspace.__PAGE__.txt').read_text() == 'strategy page'
    # Linux layout is already flat: nothing changes.
    assert module.flatten_segment_payloads(root) == 0

with tempfile.TemporaryDirectory() as tmp:
    root = Path(tmp)
    build(root, {'a/__next.x/__PAGE__.txt': 'new', 'a/__next.x.__PAGE__.txt': 'old'})
    try:
        module.flatten_segment_payloads(root)
        raise AssertionError('must refuse to overwrite')
    except SystemExit as error:
        assert 'Refusing to overwrite' in str(error)
    assert (root / 'a/__next.x.__PAGE__.txt').read_text() == 'old'

print('PASS: Windows Next.js prefetch payloads are flattened; Linux output unchanged; no overwrite')
