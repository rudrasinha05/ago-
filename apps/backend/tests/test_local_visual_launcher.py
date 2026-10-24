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
    assert "Old /console/ redirects to the visual Company Map; no duplicate UI." in source


def test_visual_launcher_recovers_fresh_terminal_without_recreating_company():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago-visual.ps1").read_text(encoding="utf-8")
    assert 'if (-not $env:AGO_POSTGRES_DSN)' in script
    assert 'Read-Host "PostgreSQL password for postgres (hidden)" -AsSecureString' in script
    assert '[Uri]::EscapeDataString($password)' in script
    assert '"postgresql://postgres:${encodedPassword}@127.0.0.1:5432/ago_test"' in script
    assert 'Remove-Variable password, securePassword, encodedPassword' in script
    assert 'No PostgreSQL password entered. Nothing was changed.' in script
    assert "init-solo" not in script
    assert "python -m ago.event_runtime migrate" not in script


def test_company_map_is_the_only_organization_screen():
    root = Path(__file__).resolve().parents[3]
    workspace = (root / "apps/web/components/workspace.jsx").read_text(encoding="utf-8")
    company = (root / "apps/web/components/company-map.jsx").read_text(encoding="utf-8")
    signin = (root / "apps/web/components/session.jsx").read_text(encoding="utf-8")
    assert workspace.count("<CompanyMap ") == 1
    assert "Advanced organization controls" not in workspace
    assert "<CompanyApprovals api={api} me={me}/>" not in workspace
    assert "router.push('/organization/#company-approval-inbox')" in workspace
    assert 'href="/console/"' not in workspace
    assert 'href="/console/"' not in signin
    assert company.count("<CommandBrain ") == 1
    assert company.count("<CompanyApprovals ") == 1
    assert "api.request('/v1/organization/departments'" in company
    assert "Create department" in company


def test_old_console_urls_default_to_one_visual_company_map(monkeypatch):
    from fastapi.testclient import TestClient
    from ago.main import create_app
    monkeypatch.delenv("AGO_LEGACY_CONSOLE_TEST_MODE", raising=False)
    with TestClient(create_app()) as client:
        for path in ("/console", "/console/"):
            response = client.get(path, follow_redirects=False)
            assert response.status_code == 308
            assert response.headers["location"] == "/workspace/organization/"
            assert "no-store" in response.headers["cache-control"]
        assert client.get("/console/assets/index.html").status_code == 404
        assert client.get("/v1/console/me").status_code == 401


def test_deleted_console_cannot_return_even_if_legacy_flag_set(monkeypatch):
    from fastapi.testclient import TestClient
    from ago.main import create_app
    monkeypatch.setenv("AGO_ENVIRONMENT", "development")
    monkeypatch.setenv("AGO_LEGACY_CONSOLE_TEST_MODE", "true")
    with TestClient(create_app()) as client:
        response = client.get("/console/", follow_redirects=False)
        assert response.status_code == 308
        assert response.headers["location"] == "/workspace/organization/"
        assert client.get("/console/assets/app.js").status_code == 404


def test_legacy_console_redirect_follows_through_to_real_visual_frontend(monkeypatch):
    from fastapi.testclient import TestClient
    from ago.main import create_app
    monkeypatch.delenv("AGO_LEGACY_CONSOLE_TEST_MODE", raising=False)
    with TestClient(create_app()) as client:
        if client.get("/workspace/organization/").status_code == 404:
            import pytest
            pytest.skip("Next.js static export not yet packaged by this test job")
        for address in ("/console", "/console/"):
            response = client.get(address, follow_redirects=True)
            assert response.status_code == 200
            assert response.url.path == "/workspace/organization/"
            assert "Organization ID" in response.text
            assert "People & departments" not in response.text
        for address in (
            "/workspace/", "/workspace/organization/", "/workspace/strategy/",
            "/workspace/governance/", "/workspace/knowledge/", "/workspace/tools/",
            "/workspace/calendar/", "/workspace/twin/",
        ):
            response = client.get(address)
            assert response.status_code == 200, address
            assert "Work email" in response.text, address


def test_normal_founder_launch_forces_single_visual_frontend():
    root = Path(__file__).resolve().parents[3]
    for relative in ("scripts/ago-visual.ps1", "scripts/ago.ps1"):
        source = (root / relative).read_text(encoding="utf-8")
        assert "AGO_LEGACY_CONSOLE_TEST_MODE" not in source


def test_approved_internal_watch_is_bounded_and_never_auto_started():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert '"watch-approved-internal"' in script
    assert "--watch-minutes 60 --limit 10 --interval-seconds 15" in script
    assert "EXECUTE_APPROVED_INTERNAL_TASKS" in script
    assert "Ctrl+C" in script
    assert "if ($Action -in @" in script
    assert "scheduled task" not in script.lower()
    assert "Start-Job" not in script


def test_approved_local_launcher_uses_hidden_founder_login_not_copied_browser_token():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    approved = [line for line in script.splitlines()
                if "python ../../scripts/local_approved_agent_batch.py" in line]
    assert len(approved) == 3
    assert all("--login" in line for line in approved)
    assert "Bearer " not in script


def test_founder_operator_exports_only_a_review_candidate_without_auto_run():
    root = Path(__file__).resolve().parents[3]
    text = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert '"export-candidate"' in text
    assert "ago_pull_candidate.py" in text
    assert "--apply --confirm EXPORT_APPROVED_AI_CANDIDATE" in text
    assert 'Read-Host "Exact completed AGO agent run ID (UUID)"' in text
    assert "Github token" not in text


def test_founder_candidate_path_is_private_and_not_inside_git_worktree():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert 'Join-Path $HOME ".ago\\candidate_exports"' in script
    assert 'Join-Path $ExportDirectory ("ago-run-" + $RunId + ".json")' in script
    assert "New-Item -ItemType Directory -Path $ExportDirectory" in script


def test_opt_in_visual_engineering_uses_only_installed_ollama_and_reverts_flags():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago-visual.ps1").read_text(encoding="utf-8")
    assert "[switch]$Engineering" in script
    assert '[string]$Model = "qwen2.5-coder:1.5b"' in script
    assert "if ($Engineering)" in script
    assert 'ago-ollama-check.ps1" -Model $Model' in script
    for setting in (
        "AGO_LLM_PROVIDER", "AGO_ENABLE_LOCAL_MODELS", "AGO_LLM_MODEL",
        "AGO_LOCAL_COMPANY_CHAIN", "AGO_LOCAL_FULL_BOARD_REVIEW",
        "AGO_LOCAL_ENGINEERING_CANDIDATES",
    ):
        assert f'$env:{setting} = ' in script
        assert f'"{setting}"' in script
    assert '$PreviousModelFlags[$Flag]' in script
    assert '[Environment]::SetEnvironmentVariable(' in script
    assert '"Process"' in script
    assert 'if ($env:AGO_ENABLE_PAID_MODELS -eq "true")' in script
    assert 'ollama pull' not in script
    assert 'Start-Process ollama' not in script


def test_operator_has_separate_fail_closed_real_engineering_dispatch():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert '"run-approved-engineering"' in script
    assert '$Coding = $Action -eq "run-approved-engineering"' in script
    assert '$CodingCheck += "--require-engineering"' in script
    assert '--login @CodingCheck --apply' in script


def test_windows_operator_has_single_reachable_complete_action_chain():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    for action in ("export-candidate", "safe-reconcile", "market-watch", "serve"):
        assert script.count(f'if ($Action -eq "{action}")') == 1
    assert script.count("finally {") == 1
    assert "if ($RunId -notmatch '^[0-9a-fA-F-]{36}$') {" in script
    assert 'ago_pull_candidate.py' in script
    assert "PRIVATE FOUNDER" not in script
    assert script.rstrip().endswith("finally {\n    Pop-Location\n}")


def test_exported_candidate_has_one_digest_pinned_docker_qa_operator_action():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert script.count('if ($Action -eq "test-exported-candidate")') == 1
    assert "--expected-candidate-sha256 $Digest" in script
    assert "--apply --confirm STAGE_TEST_AND_PREPARE_QA" in script
    assert script.index('Read-Host "To run untrusted code in offline Docker') < script.index(
        "--expected-candidate-sha256 $Digest"
    )
    assert 'if ($Preview.input_kind -cne "board_record"' in script
    assert 'Join-Path $HOME ".ago\\delivery_runs"' in script
    assert 'NewGuid().ToString("N")' in script
    assert script.count("finally {") == 1


def test_repair_operator_has_two_distinct_confirmed_unprivileged_gates():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago-repair.ps1").read_text(encoding="utf-8")
    assert 'ValidateSet("preview", "propose", "retest")' in script
    assert script.count("finally {") == 2
    assert "--staged-directory $FailedStage" in script
    assert "--repair-from $FailedStage" in script
    assert "--expected-candidate-sha256 $Digest" in script
    assert "PROPOSE_ONE_LOCAL_SOURCE_REPAIR" in script
    assert "RETEST_REVIEWED_SOURCE_REPAIR" in script
    assert "STAGE_TEST_AND_PREPARE_QA" in script
    assert "AGO_LOCAL_REPAIR_PROPOSALS" in script
    assert "ago-ollama-check.ps1" in script
    assert "if ($Mode -eq \"preview\")" in script
    assert "github_adapter" not in script
    assert "git push" not in script


def test_failed_docker_result_prints_exact_recovery_stage_for_operator():
    root = Path(__file__).resolve().parents[3]
    script = (root / "scripts" / "ago.ps1").read_text(encoding="utf-8")
    assert "retain for a source-only repair if tests fail" in script
    assert script.index('Write-Host "Docker execution stage') < script.index(
        "--expected-candidate-sha256 $Digest"
    )
