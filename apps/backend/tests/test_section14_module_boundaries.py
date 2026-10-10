"""Section 14 regression suite: real package architecture and malicious edges."""
from __future__ import annotations

import datetime as dt
from pathlib import Path

from ago.architecture_guard import load_policy, to_dot, verify

ROOT = Path(__file__).resolve().parents[1] / "ago"


def fixture_policy() -> dict:
    return {
        "schema_version": 1,
        "layers": {
            "composition": [
                "composition", "transport", "service",
                "persistence", "domain", "foundation",
            ],
            "transport": [
                "transport", "service", "persistence", "domain", "foundation",
            ],
            "service": ["service", "persistence", "domain", "foundation"],
            "persistence": ["persistence", "domain", "foundation"],
            "domain": ["domain", "foundation"],
            "foundation": ["foundation", "domain"],
        },
        "nodes": {
            "__init__": {
                "context": "entrypoints", "layer": "composition", "imports": [],
            },
            "entry": {
                "context": "entrypoints", "layer": "composition",
                "imports": ["strategy"],
            },
            "strategy": {
                "context": "strategy", "layer": "domain", "imports": [],
            },
            "audit": {
                "context": "governance", "layer": "persistence", "imports": [],
            },
            "transport": {
                "context": "transport", "layer": "transport", "imports": [],
            },
        },
        "protected_sql_writers": {
            "ago_approval_requests": ["audit"],
            "ago_task_reviews": ["audit"],
        },
        "exceptions": [],
    }


def fixtures(tmp_path, source_overrides=None):
    modules = {
        "__init__": "",
        "entry": "from ago.strategy import Strategy\n",
        "strategy": "class Strategy: pass\n",
        "audit": "class Audit: pass\n",
        "transport": "class Api: pass\n",
    }
    modules.update(source_overrides or {})
    for name, source in modules.items():
        (tmp_path / f"{name}.py").write_text(source, encoding="utf-8")
    return fixture_policy()


def codes(report):
    return {issue.code for issue in report.violations}


def test_real_project_has_no_unauthorized_edges_or_cycles():
    report = verify(ROOT, load_policy())
    assert report.passed, report.as_dict()
    assert report.modules >= 70
    assert len(report.edges) >= 140


def test_new_edge_requires_reviewed_policy_exception(tmp_path):
    policy = fixtures(tmp_path, {
        "strategy": "from ago.audit import Audit\n",
    })
    report = verify(tmp_path, policy)
    assert "forbidden-edge" in codes(report)
    assert "layer-violation" in codes(report)


def test_allowed_direction_still_requires_specific_approved_edge(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": "from ago.strategy import Strategy\nfrom ago.audit import Audit\n",
    })
    report = verify(tmp_path, policy)
    assert "forbidden-edge" in codes(report)
    assert "layer-violation" not in codes(report)


def test_legal_edge_without_import_is_stale(tmp_path):
    policy = fixtures(tmp_path, {"entry": "class Entry: pass\n"})
    assert "stale-approved-edge" in codes(verify(tmp_path, policy))


def test_new_module_cannot_bypass_explicit_registration(tmp_path):
    policy = fixtures(tmp_path, {
        "new_agent": "from ago.strategy import Strategy\n",
    })
    assert "unregistered-module" in codes(verify(tmp_path, policy))


def test_unknown_ago_module_import_is_rejected(tmp_path):
    policy = fixtures(tmp_path, {
        "strategy": "from ago.foreign_scope import Other\n",
    })
    assert "unregistered-import" in codes(verify(tmp_path, policy))


def test_from_ago_import_module_and_relative_imports_are_checked(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": "from ago import strategy\nfrom . import audit\n",
    })
    policy["nodes"]["entry"]["imports"] = ["strategy", "audit"]
    assert verify(tmp_path, policy).passed


def test_unknown_dynamic_import_call_fails_closed(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": 'from ago.strategy import Strategy\n'
                 'import importlib\n'
                 'mod = importlib.import_module(user_supplied_module)\n',
    })
    assert "unreviewable-dynamic-import" in codes(verify(tmp_path, policy))


def test_reviewed_literal_dynamic_module_still_needs_baseline(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": 'import importlib\n'
                 'mod = importlib.import_module("ago.strategy")\n',
    })
    assert verify(tmp_path, policy).passed


def test_circular_dependencies_blocked_even_when_both_edges_approved(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": "from ago.strategy import Strategy\n",
        "strategy": "from ago.entry import Entry\n",
    })
    policy["nodes"]["strategy"]["imports"].append("entry")
    report = verify(tmp_path, policy)
    assert "circular-dependency" in codes(report)
    assert "layer-violation" in codes(report)


def test_governance_tables_deny_unowned_write(tmp_path):
    policy = fixtures(tmp_path, {
        "transport": '''def bypass(db):
    db.execute("UPDATE ago_approval_requests SET status='approved'")
''',
    })
    assert "protected-sql-write" in codes(verify(tmp_path, policy))


def test_quality_reviews_deny_unowned_insert(tmp_path):
    policy = fixtures(tmp_path, {
        "strategy": '''def bypass(db):
    db.execute("INSERT INTO public.ago_task_reviews (id) VALUES (1)")
''',
    })
    assert "protected-sql-write" in codes(verify(tmp_path, policy))


def test_owned_repository_is_allowed_to_write_review_records(tmp_path):
    policy = fixtures(tmp_path, {
        "audit": '''def store(db):
    db.execute("INSERT INTO ago_task_reviews (id) VALUES (1)")
''',
    })
    assert verify(tmp_path, policy).passed


def test_exception_requires_independent_review_and_expiry(tmp_path):
    policy = fixtures(tmp_path, {
        "entry": "from ago.strategy import Strategy\nfrom ago.audit import Audit\n",
    })
    record = {
        "source": "entry", "target": "audit",
        "reason": "Constrained temporary test dependency for governance data audit",
        "change_request": "ARCH-1001",
        "author": "alice", "reviewed_by": "bob",
        "review_date": "2026-10-09", "expires_on": "2026-10-20",
    }
    policy["exceptions"] = [record]
    report = verify(tmp_path, policy, today=dt.date(2026, 10, 10))
    assert report.passed, report.as_dict()
    policy["exceptions"][0]["reviewed_by"] = "alice"
    assert "unreviewed-exception" in codes(
        verify(tmp_path, policy, today=dt.date(2026, 10, 10))
    )
    policy["exceptions"][0]["reviewed_by"] = "bob"
    policy["exceptions"][0]["expires_on"] = "2026-10-10"
    assert "expired-exception" in codes(
        verify(tmp_path, policy, today=dt.date(2026, 10, 10))
    )


def test_waiver_cannot_bypass_layer_direction_or_circularity(tmp_path):
    policy = fixtures(tmp_path, {
        "strategy": "from ago.transport import Api\n",
    })
    policy["exceptions"] = [{
        "source": "strategy", "target": "transport",
        "reason": "This edge should never be authorized despite review metadata",
        "change_request": "ARCH-4000",
        "author": "alice", "reviewed_by": "bob",
        "review_date": "2026-10-09", "expires_on": "2026-10-20",
    }]
    report = verify(tmp_path, policy, today=dt.date(2026, 10, 10))
    assert "layer-violation" in codes(report)


def test_unused_exception_blocks_permanent_blanket_permission(tmp_path):
    policy = fixtures(tmp_path)
    policy["exceptions"] = [{
        "source": "entry", "target": "audit",
        "reason": "This permission is unused and must be deleted from the baseline",
        "change_request": "ARCH-4001",
        "author": "alice", "reviewed_by": "bob",
        "review_date": "2026-10-09", "expires_on": "2026-10-20",
    }]
    assert "stale-exception" in codes(
        verify(tmp_path, policy, today=dt.date(2026, 10, 10))
    )


def test_graphviz_export_is_deterministic_and_bounded(tmp_path):
    policy = fixtures(tmp_path)
    report = verify(tmp_path, policy)
    assert report.passed
    dot = to_dot(report, policy)
    assert '"entry" -> "strategy";' in dot
    assert "digraph AGO_Module_Dependencies" in dot
    assert dot == to_dot(report, policy)


def test_invalid_policy_context_and_removed_modules_cannot_be_ignored(tmp_path):
    policy = fixtures(tmp_path)
    del policy["nodes"]["audit"]
    policy["nodes"]["strategy"]["context"] = "autonomous_self_editing"
    report = verify(tmp_path, policy)
    assert "unregistered-module" in codes(report)
    assert "invalid-module-policy" in codes(report)
