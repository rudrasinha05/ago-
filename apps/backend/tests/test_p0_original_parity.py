"""P0 recovered source cannot be silently replaced by the newer roadmap."""
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/check_p0_original_parity.py"


def tool():
    spec = importlib.util.spec_from_file_location("p0_parity", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_historical_roadmap_nongoals_references_and_34_source_paths():
    report = tool().audit()
    assert report["phase_count"] == 13
    assert report["original_non_goals"] == 8
    assert report["original_references"] == 10
    assert report["section_count"] == 34
    assert report["all_34_implementation_accepted"] is False
    assert report["original_bytes_rehashed_in_this_run"] is False
    assert report["section_status"]["document_reconciled"] == 3


@pytest.mark.parametrize("section", [15, 17, 18, 25, 29, 34])
def test_p0_section_trace_gaps_are_explicit_and_not_faked(section):
    data = json.loads(
        (ROOT / "docs/reports/P0_34_SECTION_SOURCE_PARITY.json").read_text()
    )
    entry = data["sections"][section - 1]
    assert entry["section"] == section
    assert (ROOT / entry["spec"]).is_file()
    assert (ROOT / entry["implementation"]).is_file()
    if section in (15, 17, 18):
        assert entry["status"] == "document_reconciled"
    if section == 25:
        assert entry["status"] == "design_only"
    if section == 34:
        assert entry["status"] == "partially_implemented"
