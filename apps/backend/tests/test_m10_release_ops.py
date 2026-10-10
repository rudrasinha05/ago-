"""M10 backup, anti-clobber, manifest verification and guarded restore tests."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ago import release_ops


SOURCE = "postgresql://ago_admin:sensitive-pass@db.example.com:5432/ago_prod"
DRILL = "postgresql://ago_drill:drill-pass@db.example.com:5432/ago_restore_drill"


class Result:
    returncode = 0


def fake_dump(args, *, env, **_kwargs):
    assert args[0] == "pg_dump"
    assert "sensitive-pass" not in " ".join(args)
    assert "--format=custom" in args
    assert env["PGPASSWORD"] == "sensitive-pass"
    out = Path(args[args.index("--file") + 1])
    out.write_bytes(b"PGDMP\x01\x02" + b"a" * 100)
    return Result()


def test_backup_requires_consent_and_can_never_overwrite_existing_archive(tmp_path):
    output = tmp_path / "ago.dump"
    with pytest.raises(PermissionError):
        release_ops.create_backup(SOURCE, output, runner=fake_dump)
    assert not output.exists()
    result = release_ops.create_backup(
        SOURCE, output, confirmed=True, runner=fake_dump,
    )
    assert result["verified"] is True
    assert result["bytes"] > 100
    manifest = output.with_suffix(".dump.manifest.json")
    assert manifest.exists()
    assert release_ops.verify_archive(output) == result
    with pytest.raises(FileExistsError):
        release_ops.create_backup(
            SOURCE, output, confirmed=True, runner=fake_dump,
        )


def test_checksum_tamper_and_symlinks_are_rejected(tmp_path):
    output = tmp_path / "verified.dump"
    release_ops.create_backup(SOURCE, output, confirmed=True, runner=fake_dump)
    original = output.read_bytes()
    output.write_bytes(original + b"tampered")
    with pytest.raises(ValueError, match="manifest"):
        release_ops.verify_archive(output)
    output.write_bytes(original)
    alias = tmp_path / "alias.dump"
    try:
        alias.symlink_to(output)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation unavailable on this filesystem")
    with pytest.raises(ValueError, match="symlink"):
        release_ops.verify_archive(alias, output.with_suffix(".dump.manifest.json"))
    with pytest.raises(ValueError, match="symlink"):
        release_ops.create_backup(SOURCE, alias, confirmed=True, runner=fake_dump)


def test_failed_backup_cleans_partial_outputs(tmp_path):
    output = tmp_path / "bad.dump"

    def fail(args, **kwargs):
        class Failure:
            returncode = 1
        return Failure()

    with pytest.raises(RuntimeError):
        release_ops.create_backup(SOURCE, output, confirmed=True, runner=fail)
    assert not output.exists()
    assert not output.with_suffix(".dump.manifest.json").exists()


def test_restore_requires_explicit_consent_and_distinct_disposable_database(tmp_path):
    archive = tmp_path / "ago.dump"
    release_ops.create_backup(SOURCE, archive, confirmed=True, runner=fake_dump)
    with pytest.raises(PermissionError):
        release_ops.restore_drill(SOURCE, DRILL, archive)
    for target in (SOURCE, SOURCE.replace("ago_prod", "ago_test"),
                   "postgresql://new:test@db.example.com/actual_prod"):
        with pytest.raises(PermissionError, match="restore"):
            release_ops.restore_drill(
                SOURCE, target, archive, confirmed=True,
            )


def test_restore_verifies_empty_target_and_migration_integrity(tmp_path, monkeypatch):
    archive = tmp_path / "ago.dump"
    release_ops.create_backup(SOURCE, archive, confirmed=True, runner=fake_dump)
    commands = []

    def runner(args, **kwargs):
        commands.append(args)
        assert args[0] == "pg_restore"
        assert "--clean" not in args and "--create" not in args
        assert "sensitive-pass" not in " ".join(args)
        return Result()

    class Rows:
        def __init__(self, value): self.value = value
        def fetchone(self): return self.value

    class Database:
        def __init__(self, existing=False): self.existing = existing
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def execute(self, sql): return Rows({"exists":1} if self.existing else None)

    monkeypatch.setattr(release_ops, "schema_integrity", lambda *_: True)
    result = release_ops.restore_drill(
        SOURCE, DRILL, archive, confirmed=True,
        runner=runner, connect=lambda *_a, **_k: Database(),
    )
    assert result["restored"] and result["schema_verified"]
    assert len(commands) == 2
    assert commands[0][1] == "--list"
    assert "--exit-on-error" in commands[1]
    assert "--single-transaction" in commands[1]
    assert "--no-owner" in commands[1]
    assert "ago_restore_drill" in commands[1]
    with pytest.raises(PermissionError, match="empty"):
        release_ops.restore_drill(
            SOURCE, DRILL, archive, confirmed=True, runner=runner,
            connect=lambda *_a, **_k: Database(existing=True),
        )


def test_release_preflight_output_cannot_expose_connection_secrets(monkeypatch):
    from ago.release_security import ReleasePolicy

    monkeypatch.setattr(ReleasePolicy, "from_environment",
                        classmethod(lambda cls, *_: ReleasePolicy(
                            "production", ("ago.example.com",), 1048576,
                        )))
    monkeypatch.setattr(release_ops, "schema_integrity", lambda *_: True)
    monkeypatch.setenv("AGO_ENVIRONMENT", "production")
    monkeypatch.setenv("AGO_POSTGRES_DSN", SOURCE)
    monkeypatch.setenv("AGO_M8_EXTERNAL_ENABLED", "false")
    monkeypatch.setenv("AGO_ENABLE_PAID_MODELS", "false")
    report = release_ops.check_release()
    serialized = json.dumps(report)
    assert report == {
        "configuration":True,"schema":True,
        "external_egress_disabled":True,"passed":True,
    }
    assert "sensitive-pass" not in serialized
    assert "db.example.com" not in serialized
    monkeypatch.setattr(release_ops, "schema_integrity",
                        lambda *_: (_ for _ in ()).throw(
                            RuntimeError("Sensitive DSN: " + SOURCE),
                        ))
    report = release_ops.check_release()
    assert report["passed"] is False
    assert "sensitive-pass" not in json.dumps(report)
