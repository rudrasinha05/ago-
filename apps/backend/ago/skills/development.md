# Software development skills

## dev.python-module-with-tests
title: Python module with unittest tests
roles: employee, cto, qa
stages: implementation, quality
keywords: python, module, function, unittest, test, tests, src, package, code
source: AGO original (Claude, 2026-11-24)
---
1. Put code in src/<name>.py; keep functions small, pure and typed. 2. Add src/__init__.py so src is a package. 3. Tests go in tests/test_<name>.py: import unittest; from src.<name> import <fn>; class <Name>Tests(unittest.TestCase) with def test_* methods. 4. Test the normal case, an edge case (empty, zero, None) and one invalid input with assertRaises. 5. Standard library only; no network, files or clock unless injected. 6. Add docs/<name>.md: what it does, one usage example. 7. Run python -m unittest discover -s tests mentally: every import must resolve.

## dev.json-code-candidate
title: Answer a code task as exact JSON files
roles: employee, cto
stages: implementation
keywords: json, files, path, content, candidate, acceptance_checks, code, answer
source: AGO original (Claude, 2026-11-24)
---
1. Output ONE JSON object only: no Markdown fences, no prose before or after. 2. Fields exactly: files (list of {path, content}) and acceptance_checks (list of short strings). 3. Escape newlines as \n and quotes as \" inside content. 4. Paths are relative: src/x.py, tests/test_x.py, docs/x.md. 5. Each file is complete and runnable, not a snippet or placeholder. 6. Acceptance checks are observable: "add(2,3) returns 5". 7. Before answering, re-read: valid JSON, all imports exist, tests import from src.

## dev.debugging
title: Debug a failing program or test
roles: employee, cto, qa
stages: implementation, quality
keywords: bug, debug, error, traceback, failing, fix, exception, crash, failure
source: AGO original (Claude, 2026-11-24)
---
1. Read the full error and traceback; the last frame in your code is the start. 2. Reproduce with the smallest input. 3. State one hypothesis, check it with a print or a test, then change one thing. 4. Fix the cause, not the symptom; never silence an exception. 5. Add a test that failed before the fix and passes after. 6. Check nearby code for the same mistake. 7. Write the cause and fix in one line for the record.

## dev.code-review
title: Review code before it ships
roles: cto, qa, employee
stages: implementation, quality, release
keywords: review, code, pull, request, pr, readability, quality, refactor
source: AGO original (Claude, 2026-11-24)
---
Check in order: 1. Does it do what the task asked, with tests proving it? 2. Correctness: edge cases, off-by-one, None, empty, errors handled. 3. Security: inputs validated, no secrets, no injection, least privilege. 4. Simplicity: shortest clear code, no dead code, good names. 5. Consistency with existing style. 6. Performance only where it matters. Give each finding a severity (must fix / should / nit) and a concrete suggestion.

## dev.javascript-typescript
title: JavaScript and TypeScript code
roles: employee, cto
stages: implementation
keywords: javascript, typescript, js, ts, node, npm, function, async, promise, module
source: AGO original (Claude, 2026-11-24)
---
1. Use ES modules and const/let; never var. 2. Prefer TypeScript types for public functions; avoid any. 3. async/await with try/catch; never leave a promise unhandled. 4. Validate input at boundaries; trust nothing from the network. 5. Small pure functions; side effects at the edges. 6. Tests with node:test or the project's runner: one behavior per test. 7. Lock dependency versions; prefer the standard library.

## dev.react-ui
title: React components
roles: employee, cto
stages: implementation
keywords: react, component, jsx, hooks, state, props, frontend, ui, next.js, nextjs
source: AGO original (Claude, 2026-11-24)
---
1. One component, one job; lift state only as high as needed. 2. Derive values instead of duplicating state; useMemo only for real cost. 3. useEffect only to sync with outside systems; clean up timers and requests. 4. Use real buttons, labels and headings for accessibility; every input has a label. 5. Handle loading, empty and error states visibly. 6. Keys from stable ids, never array index for changing lists. 7. Test what the user sees (roles, text), not internals.

## dev.rest-api
title: Design and build a REST API endpoint
roles: employee, cto
stages: architecture, implementation
keywords: api, rest, endpoint, http, route, json, request, response, fastapi, express
source: AGO original (Claude, 2026-11-24)
---
1. Resource nouns in paths, HTTP verbs for actions; plural names. 2. Validate the body with a strict schema; reject unknown fields. 3. Authenticate, then authorize per resource and tenant. 4. Return clear status codes: 200/201, 400/422 bad input, 401, 403, 404, 409 conflict. 5. Error bodies never leak stack traces or secrets. 6. Idempotency key for creates that may be retried. 7. Paginate lists; document with OpenAPI; test success and each failure.

## dev.sql-database
title: SQL schema and queries
roles: employee, cto
stages: architecture, implementation
keywords: sql, database, postgres, postgresql, table, query, schema, migration, index
source: AGO original (Claude, 2026-11-24)
---
1. Every table: primary key, NOT NULL where possible, CHECK constraints for valid values. 2. Foreign keys for relations; tenant_id in every key for multi-tenant data. 3. Migrations are forward-only and numbered; never edit an applied one. 4. Always parameterized queries; never build SQL from strings. 5. Index columns used in WHERE and JOIN; check EXPLAIN for slow queries. 6. Transactions for multi-step writes. 7. Test with real Postgres, not only mocks.

## dev.android-app
title: Android app development
roles: employee, cto
stages: architecture, implementation
keywords: android, kotlin, app, mobile, jetpack, compose, apk, gradle, java
source: AGO original (Claude, 2026-11-24)
---
1. Kotlin + Jetpack Compose; MVVM: UI, ViewModel, repository. 2. Request permissions only when needed, explain why. 3. Network and disk work off the main thread with coroutines. 4. Handle offline, slow network and process death (save state). 5. Accessibility: content descriptions, 48dp touch targets, scalable text. 6. No secrets in the APK; use a backend. 7. Unit test ViewModels; UI test key flows; test on a small and a large screen.

## dev.git-workflow
title: Git commits and branches
roles: employee, cto
stages: implementation, release
keywords: git, commit, branch, merge, github, pull, request, version, history
source: AGO original (Claude, 2026-11-24)
---
1. Small commits, one logical change each. 2. Message: short imperative subject, then why. 3. Never commit secrets, build output or large binaries; keep .gitignore current. 4. Pull before you push; resolve conflicts carefully and rerun tests. 5. Never force-push shared branches. 6. A PR describes what, why, how tested and risks. 7. Tag releases with semantic versions.

## dev.refactoring
title: Refactor safely
roles: employee, cto
stages: implementation
keywords: refactor, cleanup, simplify, duplicate, rename, structure, technical, debt
source: AGO original (Claude, 2026-11-24)
---
1. Have tests that pass before you start; add them if missing. 2. Change structure, not behavior, in small steps. 3. Rename for clarity; extract functions for repeated or long logic. 4. Delete dead code instead of commenting it out. 5. Run tests after every step. 6. Keep refactors separate from feature commits. 7. Stop when the code is clear enough for the next change.

## dev.performance
title: Make code faster
roles: employee, cto
stages: implementation, quality
keywords: performance, speed, slow, optimize, latency, memory, cache, profiling
source: AGO original (Claude, 2026-11-24)
---
1. Measure first: profile, find the real hot spot. 2. Fix the algorithm before micro-tuning (O(n^2) to O(n log n)). 3. Avoid repeated work: cache results with a clear invalidation rule. 4. Batch database and network calls; avoid N+1 queries. 5. Stream large data instead of loading it all. 6. Re-measure and record before/after numbers. 7. Keep the code readable; comment why an optimization exists.

## dev.cli-scripts
title: Command-line tools and scripts
roles: employee
stages: implementation
keywords: cli, script, command, terminal, argparse, powershell, bash, automation
source: AGO original (Claude, 2026-11-24)
---
1. argparse (Python) with --help text and safe defaults. 2. Dry-run flag for anything that changes files or systems. 3. Exit codes: 0 success, non-zero with a clear message on failure. 4. Never delete without confirmation; log what changed. 5. Paths with pathlib; work on Windows and Linux. 6. No secrets in arguments; read from environment or a prompt. 7. Test the main function directly.

## dev.web-scraping-ethics
title: Collect public web data responsibly
roles: employee, risk
stages: implementation
keywords: scraping, crawl, web, data, collect, html, parse, download
source: AGO original (Claude, 2026-11-24)
---
1. Prefer an official API or data export. 2. Check the site's terms and robots.txt; respect them. 3. Identify your client; rate-limit requests; cache results. 4. Collect only what you need; no personal data without a lawful basis. 5. Parse with a real HTML parser, not regex. 6. Handle page changes gracefully and alert on breakage. 7. Keep a record of source and date for every item.

## dev.documentation
title: Code documentation and README
roles: employee, pm
stages: implementation, release
keywords: documentation, docs, readme, guide, usage, install, comment, docstring
source: AGO original (Claude, 2026-11-24)
---
1. README: what it is, who it is for, install, run, test, configuration, license. 2. One copy-paste quick start that really works. 3. Docstrings say what and why, not how line by line. 4. Document every environment variable and default. 5. Examples over prose. 6. Keep docs next to code and update them in the same change. 7. Write for a new teammate on their first day.

## dev.dependencies
title: Choose and manage dependencies
roles: employee, cto, risk
stages: architecture, implementation
keywords: dependency, library, package, npm, pip, version, license, upgrade
source: AGO original (Claude, 2026-11-24)
---
1. Prefer the standard library; add a dependency only for real value. 2. Check license compatibility, maintenance activity and known vulnerabilities. 3. Pin versions with a lockfile. 4. Upgrade regularly in small steps with tests. 5. Remove unused packages. 6. Never install from untrusted sources. 7. Record why each major dependency was chosen.
