"""Fail closed when local confidential AGO files are tracked by software Git.

Path-only CI gate; contents are never opened or printed. Git .gitignore alone
does NOT prevent accidental forced 'git add -f' or historical commits.
"""
from __future__ import annotations

from pathlib import PurePosixPath
import re
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
SECRET_SUFFIXES = (
    ".pem", ".p12", ".pfx", ".key", ".dump", ".backup",
    ".pgdump", ".sqlite", ".sqlite3", ".age", ".asc",
)
SENSITIVE_NAME = re.compile(
    r"(?i)^(?:\.env(?:\.[^.]+)?|id_(?:rsa|dsa|ed25519)|"
    r"(?:.*[-_.])?(?:credentials?|service[-_.]?account|"
    r"private[-_.]?key|secrets?)[-_.]?[^/]*\.(?:json|ya?ml|ini|toml|txt))$"
)



def forbidden(path: str) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/"))
    parts = normalized.parts
    return (
        any(p in PRIVATE_ROOTS for p in parts)
        or any(SENSITIVE_NAME.fullmatch(part) for part in parts
               if part not in (".env.example", ".env.sample", ".env.template", ".env.dist"))
        or str(normalized).lower().endswith(SECRET_SUFFIXES)
    )


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
