"""Fail closed when local confidential AGO files are tracked by software Git.

Path-only CI gate; contents are never opened or printed. Git .gitignore alone
does NOT prevent accidental forced 'git add -f' or historical commits.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import subprocess
import sys

PRIVATE_ROOTS = frozenset({
    ".ago-private",
    "company-private",
    "company-confidential",
    "private-projects",
    "project-vault",
    "confidential-documents",
    "local-private",
})
SECRET_SUFFIXES = (".pem", ".p12", ".pfx", ".key", ".dump", ".backup")


def forbidden(path: str) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/"))
    return (bool(normalized.parts and normalized.parts[0] in PRIVATE_ROOTS)
            or str(normalized).lower().endswith(SECRET_SUFFIXES))


def main() -> int:
    tracked = subprocess.check_output(["git", "ls-files", "-z"])
    offending = sorted(x.decode("utf-8", errors="replace")
                       for x in tracked.split(b"\0") if x
                       and forbidden(x.decode("utf-8", errors="replace")))
    if offending:
        print("CONFIDENTIALITY FAILURE: tracked private paths:", file=sys.stderr)
        for item in offending:
            print("  " + item, file=sys.stderr)
        print("Do not merely delete the working file: investigate Git history and exposure.",
              file=sys.stderr)
        return 2
    print("OK: no known confidential local directory or key material is tracked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
