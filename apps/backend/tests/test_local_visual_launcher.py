"""The visual AGO workspace entrypoint must never silently serve only M9 console."""
from pathlib import Path


def test_visual_launcher_is_local_only_and_targets_real_react_company_map():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago-visual.ps1").read_text(encoding="utf-8")
    assert "company-map.jsx" in script
    assert "command-brain.jsx" in script
    assert 'npm.cmd run build --workspace "@ago/web"' in script
    assert "python scripts/package_frontend.py" in script
    assert "workspace/organization/" in script
    assert "python -m ago.local_ops doctor" in script
    assert "python -m ago.event_runtime migrate" not in script
    assert "init-solo" not in script
    assert "ollama pull" not in script


def test_existing_ago_operator_labels_basic_and_visual_ui_separately():
    root = Path(__file__).resolve().parents[3]
    source = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert "Visual Company Map:" in source
    assert "The basic /console/ is NOT the circular Company Map." in source
