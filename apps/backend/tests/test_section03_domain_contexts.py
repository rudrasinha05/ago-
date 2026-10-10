"""Complete context coverage and unauthorized cross-context SQL/import regression."""
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('domain_contexts', ROOT / 'scripts/check_domain_contexts.py')
ddd = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ddd)


@pytest.fixture
def copy_system(tmp_path):
    shutil.copytree(ROOT / 'apps/backend/ago', tmp_path / 'apps/backend/ago')
    shutil.copytree(ROOT / 'docs', tmp_path / 'docs')
    return tmp_path


def test_every_module_context_and_sql_boundary_matches_source():
    assert ddd.check() == []


def test_unapproved_cross_context_sql_read_is_rejected(copy_system):
    path = copy_system / 'apps/backend/ago/goals.py'
    path.write_text(path.read_text() + '\nUNAPPROVED = "SELECT * FROM ago_agent_runs"\n')
    assert 'unreviewed-sql-access' in ddd.check(copy_system)


def test_unapproved_cross_context_import_is_rejected(copy_system):
    path = copy_system / 'apps/backend/ago/credits.py'
    path.write_text(path.read_text() + '\nimport ago.knowledge_store\n')
    assert any(e.startswith('module-boundary:') for e in ddd.check(copy_system))


def test_context_owner_reassignment_is_rejected(copy_system):
    path = copy_system / ddd.CONTRACT
    contract = json.loads(path.read_text())
    contract['modules']['goals'] = 'economics'
    path.write_text(json.dumps(contract))
    assert 'context-module-drift' in ddd.check(copy_system)


def test_incomplete_context_contract_is_rejected(copy_system):
    path = copy_system / ddd.CONTRACT
    contract = json.loads(path.read_text())
    del contract['contexts']['governance']['invariants']
    path.write_text(json.dumps(contract))
    assert 'incomplete-context:governance' in ddd.check(copy_system)
