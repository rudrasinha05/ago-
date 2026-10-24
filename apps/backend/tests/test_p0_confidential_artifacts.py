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


def test_nested_dotenv_variants_case_insensitive_paths_and_cloud_tokens_blocked():
    check = load()
    dangerous = [
        ".env.production.local", "nested/.env.staging.backup",
        "apps/backend/.ENV.PRODUCTION.local", "company/PRIVATE-PROJECTS/brief.md",
        "nested/.ssh/id_ecdsa", ".aws/credentials", ".azure/accessTokens.json",
        "user/.kube/config", "nested/.npmrc", "nested/.pypirc",
        "nested/.netrc", "nested/kubeconfig", "nested/SECRETS-2026.JSON",
        "nested/credentials.TXT", "nested/.env.example.local",
        r"apps\\web\\PRIVATE-PROJECTS\\confidential.txt",
        "nested/../backup/public.md",
    ]
    for name in dangerous:
        assert check.forbidden(name), name


def test_safe_example_dotenv_files_and_normal_source_are_not_blocked():
    check = load()
    safe = [
        ".env.example", ".env.sample", ".env.template", ".env.dist",
        "examples/.env.example", "apps/web/.env.template",
        "docs/architecture/SECTION_10_SECURITY_ARCHITECTURE.md",
        "deploy/docker/Dockerfile",
    ]
    for name in safe:
        assert not check.forbidden(name), name


def test_ci_failure_does_not_print_private_paths(monkeypatch, capsys):
    check = load()
    confidential = b"client/PRIVATE-PROJECTS/FounderAcquisitionPlan.txt"
    monkeypatch.setattr(
        check.subprocess, "check_output",
        lambda arguments: confidential + bytes([0]) + b"nested/.env.production.local" + bytes([0]),
    )
    assert check.main() == 2
    output = capsys.readouterr()
    assert "CONFIDENTIALITY FAILURE" in output.err
    assert "FounderAcquisitionPlan" not in output.err
    assert ".env.production.local" not in output.err
    assert "PRIVATE-PROJECTS" not in output.err
    assert not output.out
