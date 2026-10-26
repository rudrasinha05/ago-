"""AGO's Founder one-click local launch must not remove human authority or data."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def _startup():
    return (ROOT / "scripts" / "ago-start.ps1").read_text(encoding="utf-8")


def test_double_click_entrypoint_is_only_a_local_start():
    wrapper = (ROOT / "START_AGO.cmd").read_text(encoding="utf-8")
    assert 'cd /d "%~dp0"' in wrapper
    assert 'powershell.exe -NoProfile -File "%~dp0scripts\\ago-start.ps1"' in wrapper
    assert "pause" in wrapper
    for forbidden in ("git reset", "git clean", "migrate", "ollama pull",
                      "docker pull", "AGO_FOUNDER_SOLO_APPROVAL=true"):
        assert forbidden not in wrapper


def test_start_skips_dirty_git_sync_but_still_opens_existing_company():
    ps = _startup()
    assert "git status --porcelain" in ps
    assert "if ($Update)" in ps
    assert "if ($LocalChanges.Count -gt 0)" in ps
    assert "Update skipped: modified files are preserved" in ps
    assert "Local Git changes preserved." in ps
    assert '& "$PSScriptRoot\\ago-sync.ps1"' in ps
    assert 'git branch --show-current' in ps
    assert '$Branch -cne "develop"' in ps
    assert '& "$PSScriptRoot\\ago-visual.ps1" -Engineering -Model $Model -Port $Port' in ps
    assert ps.index("if ($LocalChanges.Count -gt 0)") < ps.index(
        '& "$PSScriptRoot\\ago-sync.ps1"'
    )
    for destructive in ("git reset", "git clean", "git stash push",
                        "git switch", "git checkout", "git push", "git pull --rebase"):
        # Comments explicitly deny reset/stash; do not use command execution lines.
        assert not any(
            line.lstrip().startswith(("& ", "git ")) and destructive in line
            for line in ps.splitlines()
        )


def test_local_credentials_permissions_and_paid_models_remain_guarded():
    ps = _startup()
    assert 'notin @("development", "test", "testing")' in ps
    assert '$env:AGO_ENABLE_PAID_MODELS = "false"' in ps
    assert "if ($SoloFounder)" in ps
    assert '$env:AGO_FOUNDER_SOLO_APPROVAL = "true"' in ps
    assert '$Previous = @{' in ps
    assert "[Environment]::SetEnvironmentVariable($Name, $Previous[$Name], \"Process\")" in ps
    assert 'Join-Path $env:LOCALAPPDATA "Programs\\DockerDesktop\\resources\\bin"' in ps
    assert "PATH fixed for this session." in ps
    assert "Docker CLI not found. AGO UI can start" in ps
    assert "AGO_POSTGRES_DSN" not in ps  # Existing guarded visual launcher owns DB setup.
    assert "init-solo" not in ps
    assert "ago.event_runtime migrate" not in ps
    assert "Start-Job" not in ps
