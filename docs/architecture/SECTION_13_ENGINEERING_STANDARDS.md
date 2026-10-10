# Section 13: engineering and compatibility standard

Scope: current personal-use modular monolith. Standards are reviewable rules, backed by named gates; no external certification claim.

## Languages and ownership

Python 3.11/3.14 CI and independent 3.12: snake_case modules/functions/variables, PascalCase classes, UPPER_CASE constants, explicit domain types and typed repository ports. Keep pure domain rules free of HTTP and SQL. Transport validates input and derives tenant/authority from signed sessions; context-owned repositories perform writes. Ruff's selected E4/E7/E9/F baseline is enforced; line length 100 is a review convention, not a falsely claimed enforced formatter. Avoid broad new lint adoption that silently rewrites historical code.

JavaScript/JSX: camelCase functions/variables, PascalCase React components, named ES module exports. Canonical UI and session code lives in packages/ui and packages/sdk; regenerate Python console adapters with sync_console_adapters.py. Shared React controls remain keyboard accessible with labels, native forms, focus and live notices. Node syntax and unit tests, actual Next.js exports, Playwright and axe enforce behavior; no browser token persistence.

SQL: numbered additive migrations, snake_case identifiers, tenant composite foreign keys, indexes for bounded reads, explicit transaction ownership. A migration is immutable after publication because checksums are recorded. Never edit an applied migration to fix a later defect: add the next migration. Schema rollback means a verified compatible code version or an isolated restored copy, never automatic destructive live restore. UTC timestamps and stable capture order govern historical evidence.

Documentation/configuration: UTF-8 Markdown and structured JSON with version and source paths. Avoid undocumented dynamic imports and dynamic SQL. Source inventory, contract manifests and generated adapters must match implementation.

## Errors and logs

400 invalid bounded domain input; 401 missing/invalid session; 403 unauthorized, self approval, weakening policy or pending review; 404 missing tenant-scoped resource; 409 existing conflict where the current contract defines it; 422 malformed strict transport input; safe 500 for unexpected failures. Preserve the existing correlated error envelope and x-request-id, rather than claiming RFC9457 adoption. Never return SQL/provider exceptions, secrets, passwords, tokens or MFA material. Logs carry UTC/runtime timestamp, level, logger and request context; audit evidence remains distinct from diagnostic logs. Debug payload logging is prohibited.

## Test and coverage policy

Freeze before acceptance: whole root ago package statement coverage >=70%; governance, strategy and workforce contexts each >=75%. No module omissions or pragma exclusions are added for this batch. Coverage measures executed source statements, not correctness. Existing source ownership determines groups; missing files/groups or zero executable statements fail the checker. Real PostgreSQL CI is required for acceptance; local skipped tests are not database evidence.

Positive and negative acceptance includes old request compatibility, exact-action human approvals, self-review denial, unauthorized/read-only mutation denial, tenant isolation, immutable audit/evidence, failed/unknown handlers, stale child DNA and before/after chronology. Keep actual model/Redis/private-byte recovery gates, independent backend runs and complete browser regressions. Add realistic performance tests only for bounded delivered endpoints: 20-source historical reflection p95 over five warmed reads <3 seconds in disposable CI database; record machine-dependent limits. This is a regression budget, not a production SLA.

Gate commands: python -m ruff check; python -m pytest --cov=ago --cov-report=json; python scripts/check_engineering_quality.py --coverage PATH; all existing architecture/contract, SDK/JS/browser/build/Docker/recovery jobs. At least one full configured CI coverage run is mandatory.

## Compatibility and release versioning

The public surface is /v1 REST/OpenAPI, versioned event envelopes, SDK helpers and operator commands. Repository package versions currently remain 0.1.0 development baselines; each published application revision is identified by immutable Git SHA and matching migration/object manifest. This batch is a development revision, not a republished public package release.

For future distributable releases use MAJOR.MINOR.PATCH: additive compatible functionality increments minor, compatible fixes patch, breaking stable public surface major. During 0.y.z development breaking changes still require documented compatibility review and a minor increment; do not use pre-1.0 status to silently break clients. Deprecate before removal, name the replacement and retain at least one approved migration release. No scheduled removal without owner acceptance.

The frozen OpenAPI contract tracks current routes/methods, request fields/types/required flags/constraints and response schemas; the gate rejects silent changes until explicit review updates the manifest. Legacy three-threshold DNA requests remain valid, and old snapshot digests use their original stored scoring profile/metrics. New charter/scope/provenance fields are additive. Event schema versions retain existing replay/idempotency requirements. A passing schema gate does not replace actual authentication and PostgreSQL contract tests.
