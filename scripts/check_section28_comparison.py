"""Offline source/evidence integrity for original Section28, not a product ranking."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def check(root=ROOT, catalog=None):
    item = catalog or json.loads((root / "docs/architecture/section28_claims.json").read_text())
    errors = []
    expected = {"crewai", "autogen", "langgraph", "openhands", "bpm", "erp", "project"}
    sources = item.get("sources", [])
    if {s["id"] for s in sources} != expected or len(sources) != len(expected):
        errors.append("comparison-source-coverage")
    hosts = {"docs.crewai.com", "microsoft.github.io", "docs.langchain.com",
             "docs.openhands.dev", "docs.camunda.io", "www.odoo.com", "www.atlassian.com"}
    if any(urlsplit(s["url"]).scheme != "https" or urlsplit(s["url"]).hostname not in hosts
           or not s.get("version") for s in sources):
        errors.append("primary-source-required")
    if item.get("source_subsections") != [f"28.{n}" for n in range(1,13)]:
        errors.append("original-source-crosswalk")
    for c in item.get("claims", []):
        if c.get("kind") != "bounded_contract" or not c.get("evidence"):
            errors.append("unsupported-claim")
        if not set(c.get("sources", [])).issubset(expected):
            errors.append("unknown-source")
        for p in c.get("evidence", []):
            path = (root / p).resolve()
            if not path.is_relative_to(root.resolve()) or not path.is_file():
                errors.append("missing-evidence")
    if len(item.get("claims", [])) != 5 or len(item.get("limits", [])) < 4:
        errors.append("claim-boundaries")
    return sorted(set(errors))


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    failures = check()
    print(json.dumps({"section":28,"passed":not failures,"violations":failures,
                      "performance_superiority_tested":False}))
    raise SystemExit(2 if failures else 0)
