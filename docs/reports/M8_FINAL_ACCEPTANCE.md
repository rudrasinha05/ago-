# AGO M8 — Final Backend Acceptance

**Status: M8 Enterprise Tools, Department Automation & Integrations — ACCEPTED
IN ISOLATED GITHUB CI.** This is a defined backend milestone and does not
certify the full enterprise architecture, a general agent/tool marketplace,
real SaaS OAuth integrations, a hosted frontend or production release.

## Verified automated evidence (2026-10-10)

- Verified functional source commit: `3c9a2be78d203fb86708eabbc0b691e09062b2cf`
- GitHub Actions run: https://github.com/rudrasinha05/ago-/actions/runs/38018513545
- Python 3.11: **202 passed, zero failed, zero skipped, 1 nonblocking Starlette warning**.
- Python 3.14: **202 passed, zero failed, zero skipped, 1 nonblocking warning**.
- PostgreSQL 16: ordered SQL migrations **001–018 applied**, including
  `018_enterprise_tooling.sql`.
- Ruff: **All checks passed** on both Python versions.
- Original M1–M7 backend tests remain green.

## Six accepted backend gates

1. **Trusted catalog:** three server-registered tools, exactly
   `tool:scorecard`, `tool:knowledge_digest` and `tool:external_metrics`.
   No arbitrary code, unsafe side-effect handlers, caller-provided URL,
   dynamic plugin loading or broad external write permission.
2. **Scoped human-approved enrollment:** immutable tenant-specific proposed,
   active, rejected or disabled history, M2 reviewer consent, DB transition
   checks, a single active/pending enrollment per tool and audit.
3. **One-shot governed execution:** human operator and per-task M2 approval,
   active enrollment, transactional single task claim, terminal success/failure,
   capped output, independent QA requirement, append-only execution evidence,
   and uncertain stale-run recovery with no automatic replay.
4. **Department automation:** verified source proof (`knowledge_verified`
   or `qa_pass`), tenant/department/AI-assignee checks, deterministic
   idempotent firings, independently approvable new governed tasks and
   prevention of recursive task-trigger loops. Disabled enrollments are
   excluded from scans.
5. **Optional external read-only adapter:** HTTPS fixed-path GET with operator
   opt-in, no redirects, timeout, size and numeric telemetry validation,
   generic failure surfaces and no network calls in test CI. Enabled by
   neither tenant enrollment nor task approval alone.
6. **Secure HTTP and QA:** signed sessions, PostgreSQL RBAC, explicit opt-in
   migration of existing tenant grants, dynamic permission denial, cross-tenant
   isolation, negative enrollment and tamper tests, failure injection,
   recursion regression, disabled egress test, two-version CI.

## Safety boundaries and accepted exclusions

- M8's external connector is not production SSRF/DNS-rebinding protected by
  code alone. Network-level egress segregation/allowlisting, provider trust,
  secrets management and external-connector penetration testing are
  **not** complete. Keep `AGO_M8_EXTERNAL_ENABLED` false unless reviewed.
- Human approval to enroll a tool cannot approve a task. A successful tool run
  cannot be used as a QA pass without independent review.
- No payments, email sending, file deletion, arbitrary third-party writes,
  deployment, generalized computer use or model-directed tool authoring.
- These tests use PostgreSQL 16 in CI. The founder's Windows PostgreSQL 18
  environment has **not** yet locally migrated M6–M8; this is the subsequent
  one-shot founder-initiated acceptance.
- Real corporate SaaS integrations, OAuth, UI, cloud hosting, disaster recovery,
  load testing, external audit and release-readiness remain future separately
  gated deliverables (M9/M10 are proposed, not guaranteed production completion).

Authoritative scope: `docs/M8_SCOPE.md`.
Operator and one-time local pull guide: `docs/reports/M8_OPERATOR_GUIDE.md`.
All work on single `develop` branch under BDR. The user's consent is
required before operating on their local machine.
