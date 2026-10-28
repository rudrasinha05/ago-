# AGO full-stack regression audit — 28 October 2026

Scope: owner-requested review and correction across frontend and backend on
`develop`, starting at `366c64e59682d1815cf06246060189e0e61ffe9a`.
The owner explicitly requested both areas in this session. No separate assistant
was assumed to be running or to have reviewed these changes. Remote HEAD was
checked before edits and will be refreshed before pushing. No main-branch,
deployment, paid inference, or owner database changes are part of this audit.

## Confirmed defects corrected

1. **Delivery overview crash:** the route iterated `stages` before validating it.
   `stages: null` raised TypeError instead of the controlled evidence error.
   Reproduced both locally and in baseline Backend Quality run `40337624935`
   (1 failed, 1269 passed). Validate project entries and scoped stage evidence
   before linking approvals. Null, wrong-shaped, oversized and invalid stage
   records are regression-tested; no missing evidence becomes successful work.
2. **Misleading delivery state:** rejected plans and failed agent runs could be
   labelled as working, while fully QA-passed stages remained awaiting execution.
   Failures now take priority; completed, QA-passed stages are `internally_reviewed`.
   Empty stages are never reviewed, and Docker/GitHub/release verification stays
   false. Blocked work points to project review, not an unrelated QA action.
3. **Frontend authentication race:** a late failed SSO bootstrap cleared a newer
   password session. Bootstrap callbacks now verify the login epoch before
   clearing authority or setting a profile; SSO profiles receive the same basic
   validation as password profiles. Browser regression holds the SSO response
   until after a successful password login, then verifies authenticated navigation.
4. **Optional provider credential boundary:** the Responses adapter used default
   urllib proxy and redirect handling. It now ignores ambient proxy configuration
   and rejects redirects, like the localhost adapter. Tests cover 301/302/303/307/308
   and hostile proxy variables without contacting any provider or enabling paid AI.
5. **Test portability:** the proxy test now controls both environment spellings
   (urllib prefers lowercase); the health unit test explicitly checks both healthy
   and unavailable dependencies instead of requiring a developer database.
   Actual PostgreSQL integration tests remain separate and unchanged.

## Verification

- All three Next.js apps built; canonical web export packaged; exported homepage
  HTTP smoke passed.
- JavaScript SDK baseline: 42 passed.
- Backend local run after overview/auth/test portability fixes: 1033 passed,
  245 skipped (PostgreSQL unavailable), one upstream Starlette deprecation warning.
- Subsequent optional model provider/local adapter checks: 7 passed.
- Ruff and repository architecture/privacy/contract checks passed. No assertion
  was removed, no browser project skipped, and no failed gate relabelled as passing.
- Browser suite and final same-commit PostgreSQL/CI results are recorded below
  after execution; local unit results alone do not close those gates.

## Existing scope and acceptance gaps

This is a defect audit, not a new claim that all original architecture phases are
implemented. The source parity guard still reports 17 bounded-tested sections,
13 partial, 3 document-reconciled and 1 design-only. The separate 48-task ledger
still reports 6 completed, 27 partial and 15 pending; it is not the full project.

Issue #7's unified browser delivery journey and the durable per-reader notification
cursor requested in #4 remain unfinished feature work. Existing UI labels unread
tracking unavailable instead of inventing counts. No claim is made that CLI-only
Docker/export/independent-review steps have become a complete one-click journey.
Actual owner Windows startup, real owner-local Ollama execution, private candidate
Docker QA, independent human decision and AGO-origin GitHub delivery still need
their own real evidence. CI fixtures do not certify those owner-device outcomes.

## Continuation and integration with concurrent work

On resumption, remote `develop` had advanced to
`9050280fb4227cefb2d1b297964d513dc25c5f26`. All three workflows on that commit
were verified successful through GitHub. The concurrent frontend/tab, department,
timezone and polling fixes were incorporated without overwriting them; see
`CLAUDE_FULL_STACK_VERIFICATION_2026_10_28.md` for that contributor's evidence.

Additional corrections in this continuation:

- **Private project execution:** the runtime trusted a cached token's founder
  role. It now requires both the exact project's founder identity and the live
  active-human Founder appointment, before consuming task approval or running a
  model. The existing query supplies `founder_id`; the module policy and generated
  inventory explicitly register the existing security service dependency. No
  schema, approval policy or public API shape changed. Two isolated unit negatives
  and two real signed-session PostgreSQL negatives cover revoked Founder roles
  and a different Founder in the same tenant. Existing positive execution tests
  continue to exercise legitimate project dispatch.
- **Empty SSO probe:** absent handoff cookies now return HTTP 204 with no body and
  no-store caching instead of an unnecessary 401. The SDK recognizes 204 without
  parsing JSON. Supplied invalid credentials and replayed, previously redeemed
  cookies still return 401; the real SSO test now explicitly replays those cookies.
  The endpoint still uses its existing database dependency.

Before this continuation, local Chromium desktop passed 19 tests; local Firefox
failed while creating a page, before assertions. That local multi-browser run was
stopped and was not counted as successful. CI provides the browser integration
gate. The npm advisory audit returned zero known vulnerabilities for the lockfile.
