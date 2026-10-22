"""Guard routes and links against returning to legacy People & departments."""
from pathlib import Path
import importlib.util


ROOT = Path(__file__).resolve().parents[3]


def test_local_route_audit_covers_all_visual_workspaces_and_legacy_entry_points():
    src = ROOT / "scripts" / "ago_route_audit.py"
    contents = src.read_text(encoding="utf-8")
    compile(contents, str(src), "exec")
    spec = importlib.util.spec_from_file_location("ago_route_audit", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    paths = {row[0] for row in mod.CHECKS}
    assert {"/console", "/console/", "/console/assets/app.js"} <= paths
    assert "/workspace/organization/" in paths
    assert "/workspace/strategy/" in paths
    assert "/workspace/governance/" in paths
    assert "/workspace/calendar/" in paths
    assert "/v1/console/me" in paths
    assert mod.EXPECTED_MAP == "/workspace/organization/"


def test_visible_navigation_does_not_open_old_ui():
    root = ROOT
    for path in ("apps/web/components/workspace.jsx", "apps/web/components/session.jsx"):
        source = (root / path).read_text(encoding="utf-8")
        assert 'href="/console/"' not in source
        assert "window.location='/console/'" not in source
    operator = (root / "apps/backend/ago/local_ops.py").read_text(encoding="utf-8")
    assert "AGO Visual Company Map:" in operator
    assert "AGO Control Center: http" not in operator
    server = (root / "apps/backend/ago/console_host.py").read_text(encoding="utf-8")
    assert '"/workspace/organization/"' in server
    assert 'if _legacy_console_for_tests():' in server


def test_raw_company_links_respect_the_next_basepath():
    # Next Link is basePath-aware, native <a> is NOT.
    root = ROOT
    company = (root / "apps/web/components/company-map.jsx").read_text(encoding="utf-8")
    assert 'href="/tools/"' not in company
    assert company.count('href="/workspace/tools/"') == 2
    assert 'href="#company-approval-inbox"' in company
    assert 'href="#ago-project-portfolio"' in company
