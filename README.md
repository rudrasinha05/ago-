# Artificial General Organization (AGO)

AGO is a governed AI-native enterprise operating system. This repository is in early foundation development; the broader organizational intelligence modules are not yet implemented.

## Run backend locally

Requires Python 3.11+.

```bash
cd apps/backend
python -m venv .venv
# Windows PowerShell: .venv\\Scripts\\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
uvicorn ago.main:app --reload
```

Visit http://127.0.0.1:8000/docs or http://127.0.0.1:8000/health/live.

## Run tests

```bash
cd apps/backend
pytest -q
ruff check ago tests
```

## Current limitations

This is an initial, independently written foundation scaffold, **not** a migration of earlier Codex-generated code. DI currently supports named factories, three lifetimes, duplicate/missing/circular detection; it does not yet support async resource cleanup, graph-wide lifetime validation, or automatic discovery. Logging is basic correlated text output, not yet the previously specified enterprise logging system. Configuration is environment-driven and does not yet implement the full layered configuration platform. CI, Docker and production readiness have not been verified. Do not mark M1.1–M1.3 complete based on this scaffold.

See [handover](docs/PROJECT_HANDOVER.md) for the historical roadmap and source migration requirements.
