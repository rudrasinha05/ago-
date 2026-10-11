"""Primary-reference/source drift and unsupported comparative claims."""
import copy
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("comparison", ROOT / "scripts/check_section28_comparison.py")
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


def catalog():
    return json.loads((ROOT / "docs/architecture/section28_claims.json").read_text())


def test_reviewed_original_comparison_has_primary_sources_and_real_evidence():
    assert comparison.check() == []


def test_comparison_rejects_superiority_missing_sources_and_unverified_evidence():
    for mutate, expected in [
        (lambda c: c["claims"][0].update(kind="performance_superiority"), "unsupported-claim"),
        (lambda c: c["sources"].pop(), "comparison-source-coverage"),
        (lambda c: c["sources"][0].update(url="https://example.test/marketing"), "primary-source-required"),
        (lambda c: c["claims"][0].update(evidence=["../../private"]), "missing-evidence"),
        (lambda c: c.update(source_subsections=["28.1"]), "original-source-crosswalk"),
    ]:
        item = copy.deepcopy(catalog())
        mutate(item)
        assert expected in comparison.check(catalog=item)
