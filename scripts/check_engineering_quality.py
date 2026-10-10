"""Read-only Sections 12/13/15/16 decisions, compatibility and coverage gate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def fingerprint(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def api_contract():
    from ago.main import create_app
    schema = create_app().openapi()
    return {
        "version": 1,
        "operations": {f"{method.upper()} {path}": fingerprint(operation)
                       for path, methods in sorted(schema["paths"].items())
                       for method, operation in sorted(methods.items())},
        "schemas": {name: fingerprint(value) for name, value in
                    sorted(schema.get("components", {}).get("schemas", {}).items())},
    }


def coverage_errors(report, policy, modules):
    errors, totals = [], {}
    files = {Path(name).name: value["summary"] for name, value in report["files"].items()}
    for name, spec in modules.items():
        row = files.get(name + ".py")
        if row is None:
            errors.append("coverage-missing-module:" + name)
            continue
        group = totals.setdefault(spec["context"], [0, 0])
        group[0] += row["covered_lines"]
        group[1] += row["num_statements"]
    covered = sum(x[0] for x in totals.values())
    statements = sum(x[1] for x in totals.values())
    if not statements or covered * 100 / statements < policy["overall"]:
        errors.append("coverage-floor:overall")
    for context, floor in policy["contexts"].items():
        count, size = totals.get(context, [0, 0])
        if not size or count * 100 / size < floor:
            errors.append("coverage-floor:" + context)
    measured = {key: round(100 * value[0] / value[1], 2) if value[1] else None
                for key, value in totals.items()}
    measured["overall"] = round(covered * 100 / statements, 2) if statements else None
    return errors, measured


def check(root=ROOT, *, current_api=None, coverage=None):
    errors = []
    manifest = json.loads((root / "docs/architecture/section12_decisions.json").read_text())
    records = manifest.get("decisions", [])
    if manifest.get("version") != 1 or len(records) != 14:
        errors.append("decision-catalog-version-or-families")
    ids = {entry["id"] for entry in records}
    if len(ids) != len(records):
        errors.append("duplicate-adr")
    for entry in records:
        if not (root / entry["source"]).is_file() or not (root / entry["record"]).is_file():
            errors.append("adr-source-missing:" + entry["id"])
            continue
        text = (root / entry["record"]).read_text()
        for required in ("Status:", "Alternatives:", "Rationale:", "Performance consequence:",
                         "Operational consequence:", "Financial consequence:",
                         "Upgrade/replacement gate:", "Rollback:", "Supersedes:", "Evidence:"):
            if required not in text:
                errors.append("adr-incomplete:" + entry["id"] + ":" + required)
        if entry["status"] != "selected-local-baseline" or not entry["approval"]:
            errors.append("adr-unreviewable-status:" + entry["id"])
        if entry["supersedes"] is not None and entry["supersedes"] not in ids:
            errors.append("adr-unknown-supersession:" + entry["id"])
    roadmap = (root / "docs/architecture/SECTION_15_ROADMAP.md").read_text()
    for phase in range(13):
        if f"| {phase}: " not in roadmap:
            errors.append("roadmap-missing-phase:" + str(phase))
    sections = roadmap.split("## All34 sections", 1)[-1]
    for section in range(1, 35):
        if f"| {section}: " not in sections:
            errors.append("roadmap-missing-section:" + str(section))
    for document in ("SECTION_13_ENGINEERING_STANDARDS.md", "SECTION_16_ARCHITECTURE_GOVERNANCE.md",
                     "SECTION_17_PHASE_MINUS_ONE_NON_GOALS.md", "SECTION_18_REFERENCES.md",
                     "SECTION_19_20_META_DNA.md"):
        if not (root / "docs/architecture" / document).is_file():
            errors.append("missing-engineering-document:" + document)
    baseline = json.loads((root / "docs/architecture/section13_api_contract.json").read_text())
    if (current_api if current_api is not None else api_contract()) != baseline:
        errors.append("unreviewed-api-contract-drift")
    measured = None
    if coverage is not None:
        policy = json.loads((root / "docs/architecture/section13_quality.json").read_text())
        modules = json.loads((root / "apps/backend/ago/architecture_policy.json").read_text())["nodes"]
        problems, measured = coverage_errors(coverage, policy["coverage"], modules)
        errors.extend(problems)
    return sorted(set(errors)), measured


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--coverage", type=Path)
    args = parser.parse_args()
    report = json.loads(args.coverage.read_text()) if args.coverage else None
    errors, measured = check(coverage=report)
    print(json.dumps({"passed": not errors, "violations": errors, "coverage": measured}))
    raise SystemExit(2 if errors else 0)
