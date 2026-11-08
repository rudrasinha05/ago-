# AGO API Change Review — Project-scoped Durable Queue (2026-11-09)

## Purpose and authority
Founder-requested incremental AGO development: protect bounded, owner-authorized multi-project task execution from accidentally leasing higher-priority work belonging to another project. The original frozen 429-point master checklist is not changed. This change extends the existing local operations API without deleting or altering original POST payload requirements.

## Reviewed change (source SHA 53d4028)
- GET `/v1/operations/enterprise/work-queue` accepts optional `plan_id` query UUID. Without it, legacy tenant queue listing is retained.
- Existing `EnterpriseQueueClaimInput` accepts optional `plan_id` UUID for both ordinary and offline claims. Existing `lease_seconds` requirements unchanged.
- The backend applies the same active-plan and tenant-owned plan-step/task restriction atomically while granting a lease. Client filtering alone is insufficient.
- Founder local queue worker validates the selected active project through existing signed project-details endpoint and passes its exact plan ID. Applying without a project requires explicit `--all-projects`.

## Explicitly unchanged
Auth, independent task/approval checks, per-tenant access, company mode, capacities, employee scheduling, lease TTL, QA-dependency gate, unknown-outcome reconciliation, no automatic replay, financial/GitHub/release authority, existing migrations and founder local data.

## Contract evidence
GitHub CI on 53d4028 reports ONLY:
- GET work-queue operation hash: `6cf1f735dc02e64417cb514a5059cbbc68c895f0f6dc941cf86a4821ba1a79f2`
- EnterpriseQueueClaimInput schema hash: `e080a76bbbe87b311dcc277a7e4079310339eecfb41cc9492584e0aa9a976320`
- No operations or schemas removed.

Only these two entries were changed in the Section 13 API fingerprint snapshot. The existing Section 5 internal interface snapshot was updated in the implementation commit; there is no silent contract overwrite. Real disposable PostgreSQL and full CI acceptance remain separate gates.
