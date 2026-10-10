# Section 10 — Concrete Identity and Secret Operations

Status: implementation verified at `9dd3da1` by primary CI `38065558141`
and independent CI `38065558142` (all nine jobs passed); actual production
setup/evidence is unavailable. This runbook is not a claim that a vault, HTTPS ingress, encrypted
database or identity provider has been deployed. No secrets belong in GitHub,
these documents, chat, build arguments or a committed environment file.

## External vault startup and staged rotation

Configure the four non-secret Vault references in `production.env.example`.
The application token must be mounted as a private owned regular file (0600),
with an approved CA certificate. Use an operator-managed Vault agent/auth method
to renew the narrowly scoped read token; the application never owns vault policy
creation, AppRole administration or unrestricted vault write rights.

The KV-v2 bundle contains string values for `AGO_SESSION_SECRET`,
`AGO_SESSION_KEYRING`, `AGO_POSTGRES_DSN`, `AGO_MFA_KEYS` and, when required,
`AGO_OIDC_CLIENT_SECRET`. The session keyring shape is
`{"current":"key-id","keys":{"key-id":{"secret":"private value"}}}`;
retired entries must also specify integer `verify_until` no more than 900 seconds
in the future. MFA keyring shape is
`{"current":"key-id","keys":{"key-id":"base64url encoding of 32 random bytes"}}`.
At most three keys are retained; current signing secret must match the bundle's
`AGO_SESSION_SECRET`. Do not copy the illustrative strings as actual key values.

1. Create new random signing/MFA material in the actual approved external vault;
   record non-secret version/key IDs and authorized change ownership.
2. Update the bundle: new current signing key, old verification-only signing key
   with a maximum 15-minute overlap; new current MFA key plus previous decrypt key.
   Restart/roll the service to retrieve that exact bundle. Reads verify TLS/CA,
   reject redirects, deleted/destroyed versions, unsafe files and unknown fields.
3. Verify new sessions carry the new key ID; old sessions work only until their
   fixed deadline. Removing a retired key immediately rejects those sessions.
4. Authorized human calls `POST /v1/security/mfa/rotate` repeatedly until
   `reencrypted` is zero. It processes at most 100 old-key factors per request,
   skips already-current factors and invalidates pending enrollment/SSO states.
5. Wait out/restart pending flows, verify all tenants were migrated, then remove
   previous MFA keys. Run the actual production factor/sign-in/recovery drill
   and retain redacted evidence. A unit test is not that operational drill.
6. Rotate the real database credentials with the database operator, update vault,
   roll connections and revoke the prior database login after verification.

## MFA, secure onboarding and recovery

Production policy must be `mfa` or `oidc`; production startup retrieves vault
material and validates required keys/provider configuration. Password fallback
is disabled under `oidc`. Prepare initial operator MFA in a controlled private
environment before enabling public access; no silent enrollment bypass exists.

- Enrollment: an authenticated user re-enters the current password at
  `POST /v1/security/mfa/enroll`, scans the one-time otpauth URI privately and
  confirms its five-minute enrollment token plus six-digit code at
  `POST /v1/security/mfa/confirm`. The secret is encrypted with tenant/user AEAD
  binding. Confirmation invalidates older sessions and returns ten recovery
  codes once; keep them in the user's private approved password manager.
- Sign-in: send optional `factor_code` to `/v1/sessions`; both browser sign-in
  forms support this field. Every enrolled account requires a valid unused
  time step or recovery code even in development. Existing login throttling
  counts factor failures. Never persist a bearer token in browser storage.
- Invitation: an authorized human issues `/v1/security/tickets` with kind
  `invitation`, target email and existing same-tenant department. Deliver the
  one-time token to the intended employee through an approved secure channel.
  The application does not send unrequested emails. The target redeems it with
  matching email/new password at `/v1/security/tickets/redeem`, receives a
  restricted MFA enrollment proof, then confirms MFA before production sign-in.
  The created role is `member`; invitation cannot choose administrator roles.
- Recovery: a separate authorized human issues a 15-minute `recovery` ticket
  for an existing human employee. Redemption requires the matching account and
  existing MFA/recovery proof where enabled; it changes the password and bumps
  the session epoch, retaining local roles/MFA. It never disables MFA or bypasses
  OIDC policy. Lost password **and** all MFA factors require the separately
  reviewed emergency process, not an unguarded HTTP reset endpoint.
- Expired/used/revoked-issuer/stale-version tickets are rejected. New active
  ticket/enrollment records are not deleted automatically for audit convenience;
  expiry excludes them immediately. Limit operational access/retention.

## Explicit OIDC provider and browser flow

Supply approved `AGO_OIDC_CONFIG` with HTTPS issuer, authorization/token endpoints
on that issuer origin, exact client ID and application callback
`https://APP-HOST/v1/security/sso/callback`. `jwks_file` is a reviewed bounded
public RSA signing keyset; optional `ca_file` supplies the approved private-provider
CA. The provider must return RS256, a single exact client audience, fresh nonce,
auth_time and MFA amr (`mfa` or both `pwd` and `otp`). Unsupported claims/algorithms
fail closed; this is an explicit provider contract, not universal IdP discovery.

An authorized human binds the provider's stable subject to an existing local
active tenant user at `/v1/security/sso/bindings`. Provider email/roles never create
a privileged local account. Review bindings independently and retain audit IDs.
Replace pinned public keysets through a reviewed deployment before provider
rotation; retain at most five approved RSA keys. Do not download attacker token
`jku`/`x5u` URLs or compute allowed algorithms from token headers.

The workspace starts code+PKCE with S256, browser-bound state and nonce. Callback
consumes state before exchange; a failed exchange cannot replay. A 60-second
HttpOnly/Secure/SameSite cookie handoff carries only an opaque one-time ticket.
The workspace redeems that ticket, stores the signed bearer in tab memory and
clears handoff cookies. Other API calls continue to omit cookies. Docker access
logs are disabled so callback authorization codes/state do not enter URI logs;
retain redacted security audit and request-ID monitoring through the approved sink.

## HTTPS, encryption and assessment evidence

Use the existing M10 ingress/backup runbook. The real gateway must strip inbound
forwarding headers, establish trusted upstream HTTPS identity and have a public
trusted certificate/HSTS/rate limits. PostgreSQL must use verify-full plus the
approved CA. `pg_stat_ssl` proves **transport** encryption only; it does not prove
encrypted disks, encrypted backups or KMS ownership. Obtain those actual provider
attestations and perform redacted recovery/rotation drills.

Send the threat model, original checklist, final commit and passing CI, deployment
boundary/config references and relevant abuse journeys to the independent assessor
through the approved private process. Track finding owner/severity/remediation and
independent retest. Self-review and a local TLS test do not close that external gate.

Rollback: pause public ingress and pending flows; retain additive schema/audits.
Do not resume an older image that permits password fallback after production MFA/
OIDC policy has been enabled. Preserve decrypt keys until re-encryption/recovery
is verified; an invalid or unavailable vault must leave the application unavailable.
