"""Cross-package and service-boundary negative tests, without npm/network use."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('monorepo', ROOT / 'scripts/check_monorepo.py')
monorepo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monorepo)


@pytest.fixture
def copy_repo(tmp_path):
    shutil.copytree(ROOT, tmp_path / 'repo', ignore=shutil.ignore_patterns(
        '.git', 'node_modules', '.next', 'out', '__pycache__', '.pytest_cache', '*.egg-info',
    ))
    return tmp_path / 'repo'


def test_monorepo_matches_all_apps_packages_services_and_lockfile():
    assert monorepo.check() == []


def test_app_to_app_coupling_fails(copy_repo):
    path = copy_repo / 'apps/web/app/page.jsx'
    path.write_text(path.read_text() + "\nimport '@ago/admin';\n")
    assert any(e.startswith('forbidden-package-import:') for e in monorepo.check(copy_repo))


def test_relative_filesystem_escape_fails(copy_repo):
    path = copy_repo / 'packages/shared/index.js'
    path.write_text(path.read_text() + "\nimport '../../sdk/index.js';\n")
    assert any(e.startswith('filesystem-package-escape:') for e in monorepo.check(copy_repo))


def test_new_dependency_requires_review(copy_repo):
    path = copy_repo / 'packages/shared/package.json'
    package = json.loads(path.read_text())
    package['dependencies'] = {'@ago/sdk': '0.1.0'}
    path.write_text(json.dumps(package))
    assert 'package-dependencies:@ago/shared' in monorepo.check(copy_repo)


def test_unapproved_service_extraction_fails(copy_repo):
    path = copy_repo / 'services/auth/boundary.json'
    data = json.loads(path.read_text())
    data['deployment'] = 'microservice'
    path.write_text(json.dumps(data))
    assert 'service-boundary-drift:auth' in monorepo.check(copy_repo)
