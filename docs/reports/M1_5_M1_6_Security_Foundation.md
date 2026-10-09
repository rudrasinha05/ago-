# M1.5 Authentication / M1.6 Authorization — Foundation

Implemented:
- PBKDF2-HMAC-SHA256 password hash/verification with per-password random salts and bounded iteration validation.
- HMAC-signed, expiring, tenant-bound session tokens with strict signature/issuer/time validation.
- Deny-by-default role-permission policies with tenant isolation.
- Unit tests for password verification, token expiry/tampering, and cross-tenant denial.

**Security boundaries:** This is a core library, not a completed authentication system. No registration/login routes, user/role persistence, identity provider, MFA, rate limiting, token revocation, key rotation, account recovery, audit logging or session storage. Never hardcode production signing secrets. Session token format is proprietary and is NOT a JWT/OIDC implementation. Tenant IDs must come from trusted resource lookup rather than client claims. Policy grants are currently in-memory. Production use requires further design review and security testing.

Status: M1.5 and M1.6 in progress.
