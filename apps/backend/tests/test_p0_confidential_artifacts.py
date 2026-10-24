"""Tracked Git and private archive protection — no confidential path disclosure."""
import importlib.util
from pathlib import Path


def load():
    filename = Path(__file__).resolve().parents[3] / "scripts/check_confidential_artifacts.py"
    spec = importlib.util.spec_from_file_location("p0_confidential_check", filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_paths_denied_at_any_repo_depth():
    check = load()
    blocked = [
        ".env", ".env.production", "apps/backend/.env.local", "id_ed25519",
        "scripts/company-private/strategy.json", "apps/web/private-projects/x.txt",
        "backup/daily.backup", "backups/local.pgdump",
        "keys/private_key.json", "service-account.json",
        "my-credentials.yaml", "nested/project-vault/export.zip",
        "company/keys/id_rsa", "my-secret.txt",
    ]
    for name in blocked:
        assert check.forbidden(name), name


def test_safe_templates_and_source_remain_eligible():
    check = load()
    allowed = [
        "README.md", "apps/backend/ago/security_controls.py",
        "apps/web/components/company-map.jsx",
        "docs/security/SECTION10_OPERATIONS.md",
        "examples/.env.example", "deploy/docker/compose.preview.yml",
    ]
    for name in allowed:
        assert not check.forbidden(name), name
