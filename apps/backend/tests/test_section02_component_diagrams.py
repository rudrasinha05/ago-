"""Diagram source/status fidelity and source deletion/drift negative tests."""
import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location(
    "component_diagrams", ROOT / "scripts/check_component_diagrams.py",
)
diagrams = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagrams)


@pytest.fixture
def catalog():
    return json.loads((ROOT / diagrams.CATALOG).read_text())


def test_all_six_views_match_registered_source_and_generated_diagrams():
    assert diagrams.check() == []


def test_missing_component_view_fails(catalog):
    catalog["views"].pop()
    assert "view-coverage" in diagrams.validate(catalog)


def test_unknown_source_symbol_fails(catalog):
    catalog["components"]["brain"]["sources"] = ["apps/backend/ago/goals.py#InventedBrain"]
    assert "missing-source:brain" in diagrams.validate(catalog)


def test_future_oos_cannot_be_marked_as_current(catalog):
    catalog["components"]["oos"]["status"] = "bounded"
    assert "unsupported-status:oos" in diagrams.validate(catalog)


def test_future_connection_cannot_be_marked_current(catalog):
    catalog["views"][2]["edges"][0]["kind"] = "current"
    assert "unsupported-current-edge:orchestration" in diagrams.validate(catalog)


def test_unknown_relationship_endpoint_fails(catalog):
    catalog["views"][0]["edges"][0]["to"] = "unrestricted_autonomy"
    assert "invalid-edge:leadership" in diagrams.validate(catalog)


def test_edge_requires_real_symbol_evidence(catalog):
    catalog["views"][0]["edges"][0]["evidence"] = ["apps/backend/ago/goals.py#Missing"]
    assert "missing-edge-evidence:leadership" in diagrams.validate(catalog)


def test_generated_diagram_edit_fails(tmp_path):
    shutil.copytree(ROOT / "apps/backend/ago", tmp_path / "apps/backend/ago")
    shutil.copytree(ROOT / "docs", tmp_path / "docs")
    path = tmp_path / diagrams.OUTPUT
    path.write_text(path.read_text().replace("Company Brain", "Unverified AGI", 1))
    assert diagrams.check(tmp_path) == ["component-diagram-drift"]


def test_generation_is_deterministic_without_catalog_mutation(catalog):
    before = copy.deepcopy(catalog)
    assert diagrams.render(catalog) == diagrams.render(catalog)
    assert catalog == before
