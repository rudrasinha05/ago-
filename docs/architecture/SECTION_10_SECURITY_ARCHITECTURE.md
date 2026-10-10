# Section 10 — Frozen Security Architecture

The eight original checklist requirements remain authoritative. The founder
authorized completion through Section 10 in one batch and indicated existing
production configuration should be in the repository. Read-only inspection found
templates and operational runbooks, no live vault address/credentials, production
HTTPS endpoint, SSO issuer mapping, encryption-operation attestation or independent
assessment report. No corresponding AGO/VAULT/OIDC environment configuration is
available. This is an evidence/access gap, not authorization to invent success.

| Requirement | Required completion evidence |
| --- | --- |
| Authentication/RBAC/tenant | Preserve signed sessions, live database grants and cross-tenant denials under all new identity flows |
| Independent approvals | Invitation/recovery/SSO cannot grant arbitrary roles or alter governed decisions; existing independent approver and QA gates pass |
| Tamper-aware audit/revocation | Append-only security audit, credential-change session invalidation, single-use/replay protection and minimal metadata |
| External production vault/rotation | Implement verified HTTPS Vault KV-v2 adapter and private token file, key-ID rotation with bounded retired-key overlap and fail-closed reads; **actual production vault configuration/rotation drill still required** |
| Trusted HTTPS/DB encryption operations | Preserve strict HTTPS ingress/verified PostgreSQL checks, deliver concrete deploy/rotation/encryption verification procedure; **actual trusted production certificate, encrypted disk/backup evidence and operational drill still required** |
| MFA/SSO/invitation/recovery | MFA challenge with encrypted TOTP secret, replay protection, hashed single-use recovery codes; OIDC code+PKCE with browser-bound state/nonce, fixed RS256/issuer/audience and required MFA; explicit local subject binding and DB roles; secure expiring invitation, credential reset and session revocation; actual HTTP/DB/crypto and negative tests |
| External assessment/threat/compliance | Deliver concrete threat model, abuse tests, control/evidence matrix and independent assessment handoff; **independent assessor findings and closure cannot be replaced by self-authored tests** |
| Fail-closed production configuration | Missing/invalid vault, MFA key and enforced identity policy prevent startup/login; no password fallback when production SSO/MFA is required |

Implementation acceptance and production/external acceptance will be reported
separately. Existing original checkboxes will stay open wherever actual external
evidence is unavailable. No new paid account/service, public deployment or invented
certification is authorized or claimed. No secrets are printed or committed.
Rollout preserves existing development login compatibility; production requires
the configured identity policy. Recovery changes credentials and revokes existing
sessions; it cannot disable MFA or increase roles. SSO identities must be bound
by an existing authorized human; provider claims never become local permissions.

Protocol references: OpenID Connect Core 1.0 (errata set 2),
https://openid.net/specs/openid-connect-core-1_0.html ; PyJWT fixed algorithm and
required-claims guidance, https://pyjwt.readthedocs.io/en/stable/api.html ; Vault
KV-v2 API, https://developer.hashicorp.com/vault/api-docs/secret/kv/kv-v2 .
