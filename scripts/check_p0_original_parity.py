"""P0: deterministic 34-section source audit and recovered original 15/17/18 trace.

This validates a maintained source map and preserved original baseline wording.
It does not claim the remaining unimplemented enterprise features are complete.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "docs/reports/P0_34_SECTION_SOURCE_PARITY.json"
REPORT = ROOT / "docs/reports/SECTIONS15_18_SOURCE_VERIFICATION.md"
PHASES = (
    "Architecture Baseline", "Engineering Foundation",
    "Identity, Audit, and Messaging Foundation",
    "Organization and Employee Core", "Workflow and Approval MVP",
    "Memory MVP", "Execution Sandbox MVP",
    "Company Brain and Executive Council", "QA and Evaluation",
    "Communication Hub", "Simulation Lab", "Production Hardening",
    "Microservice Extraction Readiness",
)
NON_GOALS = (
    "No production code.", "No database tables.",
    "No final LLM prompt design.", "No final model/provider commitment.",
    "No UI visual design system implementation.",
    "No final deployment topology.",
    "No customer-specific compliance certification.",
    "No microservice extraction.",
)
URLS = (
    "https://fastapi.tiangolo.com/", "https://nextjs.org/docs",
    "https://www.postgresql.org/docs/", "https://docs.docker.com/compose/",
    "https://kubernetes.io/docs/", "https://kafka.apache.org/documentation/",
    "https://docs.temporal.io/", "https://opentelemetry.io/docs/",
    "https://developer.hashicorp.com/vault/docs",
    "https://qdrant.tech/documentation/",
)
HISTORICAL_SHA = "6589bc4f7e4f30287a61cefe3979b01d0b2a8357e3bb76dd6bb058d9e1daa1c4"


def audit(root: Path = ROOT) -> dict:
    report = (root / REPORT.relative_to(ROOT)).read_text(encoding="utf-8")
    if HISTORICAL_SHA not in report or "ORIGINAL SOURCE RECOVERED AND COMPARED" not in report:
        raise ValueError("Original recovered blueprint provenance changed")
    # Check every recovered historical phase in its actual table, not
    # scattered incidental words in comment text.
    rows = re.findall(r"^\\|\\s*([^|]+)\\s*\\|\\s*([^|]+)\\s*\\|", report, re.M)
    found = [label.strip() for _, label in rows]
    if any(name not in found for name in PHASES):
        raise PermissionError("One or more original 13 phases were dropped")
    if not all(goal in report for goal in NON_GOALS):
        raise PermissionError("One or more original Phase-minus-one non-goals were dropped")
    if not all(url in report for url in URLS):
        raise PermissionError("Original ten canonical technology references lost")
    if ("different" not in report or "Preserve both" not in report
            or "NOT CLAIMED" not in report):
        raise PermissionError("Historic blueprint divergence cannot be hidden")

    data = json.loads((root / INDEX.relative_to(ROOT)).read_text(encoding="utf-8"))
    if data.get("schema") != "ago_architecture_34_source_parity_v1":
        raise ValueError("Unknown immutable section-audit schema")
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) != 34:
        raise ValueError("All 34 original sections must appear exactly once")
    allowed = {"tested_bounded", "partially_implemented",
               "document_reconciled", "design_only"}
    missing = []
    for expected, section in enumerate(sections, 1):
        if (set(section) != {"section", "title", "spec", "implementation", "status"}
                or section["section"] != expected
                or section["status"] not in allowed
                or not section["title"]):
            raise PermissionError("Section audit must preserve original order and status")
        for path in ("spec", "implementation"):
            name = section[path]
            if (not isinstance(name, str) or name.startswith("/")
                    or ".." in Path(name).parts or not (root / name).is_file()):
                missing.append({"section": expected, "source": path})
    if missing:
        raise FileNotFoundError("Missing architecture-to-source evidence paths")
    if all(x["status"] == "tested_bounded" for x in sections):
        raise PermissionError("Unproven universal 34-section implementation cannot be asserted")
    counts = {status: sum(s["status"] == status for s in sections)
              for status in sorted(allowed)}
    return {"phase_count": len(PHASES), "original_non_goals": len(NON_GOALS),
            "original_references": len(URLS), "section_count": 34,
            "source_verified_from_recorded_sha": True,
            "original_bytes_rehashed_in_this_run": False,
            "section_status": counts,
            "all_34_implementation_accepted": False}


if __name__ == "__main__":
    print(json.dumps(audit(), sort_keys=True))
