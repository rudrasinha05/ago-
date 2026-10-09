"""PostgreSQL migration runner with checksum tracking and advisory locking."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


class MigrationError(RuntimeError):
    pass


def apply_migrations(connection: Any, directory: Path) -> list[str]:
    """Run ordered SQL files in one transaction; reject changed applied migrations.

    The caller supplies a psycopg connection with autocommit=True.
    """
    if not directory.is_dir():
        raise MigrationError(f"Migration directory missing: {directory}")
    applied: list[str] = []
    with connection.transaction():
        connection.execute("SELECT pg_advisory_xact_lock(819271, 1)")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS ago_schema_migrations (
                filename text PRIMARY KEY,
                sha256 text NOT NULL,
                applied_at timestamptz NOT NULL DEFAULT now()
            )"""
        )
        existing = {
            (row["filename"] if isinstance(row, dict) else row[0]):
            (row["sha256"] if isinstance(row, dict) else row[1])
            for row in connection.execute(
                "SELECT filename, sha256 FROM ago_schema_migrations"
            ).fetchall()
        }
        for file in sorted(directory.glob("*.sql")):
            digest = hashlib.sha256(file.read_bytes()).hexdigest()
            if file.name in existing:
                if existing[file.name] != digest:
                    raise MigrationError(f"Applied migration changed: {file.name}")
                continue
            connection.execute(file.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO ago_schema_migrations(filename, sha256) VALUES (%s, %s)",
                (file.name, digest),
            )
            applied.append(file.name)
    return applied
