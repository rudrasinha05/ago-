# Section 10 — Threat Model and Assessment Handoff

Version 1, 2026-10-10. This is an internal engineering threat model and control
inventory. It is **not** an external assessment, compliance certification,
production encryption attestation or permission to deploy publicly.

Assets: tenant work, private memories/documents/vectors, employee credentials,
approval and QA decisions, bearer tokens, signing/MFA keys, audit evidence and
backup archives. Trust boundaries: browser ↔ approved HTTPS ingress ↔ nonroot
backend ↔ private PostgreSQL; backend ↔ explicitly configured vault/identity
provider; human operator ↔ administrative actions and recovery; CI ↔ disposable
test services. Redis and vectors are derived data and cannot grant access.

| Threat/trigger | Engineering control and verification | Residual/operational evidence |
| --- | --- | --- |
| Tenant ID, role or approval injection | Server-derived principal; live DB grants; composite FKs; strict DTOs; independent approval and QA guards; HTTP adversarial tests | Tenant onboarding and periodic role review by owner |
| Private memory exposed by search/summary/cache | Scope predicate before ranking, identical-scope consolidation, source/version invalidation, no private graph publication; Section 9 real model/privacy tests | Privacy inventory, retention policy and subject-request procedure approved by owner |
| Stolen password / credential stuffing | Persisted bounded throttle; encrypted TOTP factor, MFA/OIDC policy and replay protection | Enforced provider MFA, secure enrollment and monitored rate/abuse response |
| Stolen/replayed session | Short TTL, DB revocation, credential epoch invalidation and rotation key deadlines | Production key custody, revocation drill and active incident monitoring |
| TOTP secret DB leak or row substitution | AEAD-encrypted factor with tenant/user associated data; private vault-managed key material | Actual external vault policy, key custody, audit sink and rotation/re-encryption evidence |
| TOTP/recovery brute force | Existing persisted login throttle applies to factor failures; bounded factor input; single-use recovery digests | Public gateway limits and alerts; independent abuse assessment |
| Login CSRF / authorization code theft | OIDC code+S256 PKCE, browser-bound single-use state, nonce, exact redirect URI and bounded auth-time/MFA | Registered production client/redirect, issuer operational assurance |
| ID token forgery / alg confusion / wrong audience | Fixed RS256, pinned issuer/client audience/keys, mandatory claims, no symmetric/asymmetric mixing | Trusted issuer signing-key rotation and compromise procedure |
| SSO privilege escalation / email collision | Explicit human-managed issuer/sub → existing tenant user mapping; provider roles ignored; active local DB roles | Independent mapping approval and periodic role/user reconciliation |
| Invitation theft / arbitrary administrator creation | Unguessable hashed token, bounded expiry, email/department binding, single use, fixed low-privilege role | Secure human delivery to intended employee; no auto-email claim |
| Recovery used to bypass factor/SSO policy | Separate authorized human issuer, short expiry, existing factor required, credential epoch bump, no role/factor reduction | Monitored secure recovery verification; emergency process reviewed by owner |
| Vault MITM / redirected credential leakage | Verified TLS and explicit CA, no redirects, fixed configured URL/path, private no-follow token file, bounded response and generic failure | Actual production vault endpoint/certificate/auth scope and renewal drill |
| Expired/removed key silently accepted | Explicit key IDs; bounded retired-session-key deadline; missing key fails closed | Documented staged rotation/rollback and evidence from production |
| Untrusted forwarded headers bypass HTTPS | Uvicorn trusts no proxy headers by default; strict trusted ingress override; HSTS/no-store perimeter | Gateway strips inbound forwarded headers and trusts only private backend path |
| Database or backup bytes stolen | TLS verify-full and exact CA required; private user and isolated checksum restore | Actual encrypted disks/backups/KMS, restricted migration/app roles and off-site retention evidence |
| Poison/out-of-order message grants authority | Token-fenced ordered leases, bounded attempts, safe dead-letter observability; no approval handler; audited human replay | Backlog/poison alert thresholds, worker provisioning and operator runbook |
| Partial crash duplicates DB effects | Transactional inbox/effect/receipt/ack and identity-based idempotency; real independent worker tests | External effects require separate provider idempotency contract |
| Log or error reveals credentials/content | Generic auth/vault/storage errors, strict validation without echoed input; no body in queue inspection; metadata-only memory audit | Approved log access, scrubbing, retention and incident evidence preservation |
| SQL injection / resource exhaustion | Parameterized SQL; UUID/length/depth/quota bounds; body cap; bounded exact vector ranking | Production resource budgets and WAF/load assessment |
| Derived summary retains corrected/forgotten fact | Correction scrubs derived summary and vector; forgetting scrubs source/ref/vector and descendants; immediate expiry exclusion | Backup retention/deletion and restore re-application of privacy tombstones |
| Audit rewrite | Protected append-only audit/receipts and migration checksum; source ownership guards | Independent audit export/retention and DB administrator accountability |
| Malicious artifact/path traversal | Opaque tenant/UUID IDs, no-follow private directories, exclusive bytes and digest/size checks | Managed encrypted volume, malware policy if executable artifact support is added |
| Compromised dependency / supply chain | Reviewed dependency bounds, actual wheel/image/build regression, no model auto-download, model manifest hashes | Base-image digests, SBOM/vulnerability review and supplier process |

## Required production evidence packet

Supply non-secret references and attestations through the approved private
channel. Never attach vault tokens, passwords, signing/MFA keys or database DSNs.

1. Public approved hostname; certificate chain/expiry; ingress config proving
   strip/replace forwarding headers, redirect/HSTS, trusted upstream and limits.
2. Vault provider/address and application policy; token/agent auth renewal and
   authorized KV path; dated signing/MFA/DB credential rotation and rollback drill.
3. PostgreSQL verify-full connection proof; encrypted-volume/KMS and encrypted
   off-site-backup evidence; separate app/migration roles; actual recovery/RTO/RPO.
4. Identity issuer/client/redirect references; verified MFA policy; explicit
   subject bindings; secure invitation/recovery and revocation operational drill.
5. Independent assessor identity, scope and dated report; severity/risk owner;
   finding remediation/retest evidence. A report written by this implementing
   assistant or passed CI cannot satisfy this independent requirement.
6. Organization-specific privacy/retention, access review, incident response,
   vulnerability handling and change-control ownership. No GDPR/SOC 2/ISO 27001
   certification is inferred from this technical inventory.

Production gates remain blocked until those actual external artifacts can be
verified. Implementation tests will be cited by their final passing commit/run;
planned tests or simulated providers are not recorded as production evidence.
