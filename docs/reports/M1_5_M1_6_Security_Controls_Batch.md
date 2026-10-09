# M1.5/M1.6 security controls — consolidated batch

Added six related building blocks:
1. PostgreSQL migration 003 for tenant role permissions, revoked sessions and security audit.
2. Persistent role permission grant/revoke and tenant-filtered permission queries.
3. SHA-256 token fingerprint storage and session revocation lookup.
4. Structured security audit persistence.
5. Thread-safe bounded in-process fixed-window rate limiter.
6. Unit tests for tenant isolation, revocation, audit, concurrency and limit resets.

**Scope limits:** The existing API router and bearer guard are not yet wired to these controls. The limiter is process-local, not distributed. Audit metadata must be redacted by callers. Tokens must be checked for revocation by the integration layer; the primitive alone does not enforce it. Migration 003 and its indexes need PostgreSQL integration verification. No claims of completed production authentication, MFA or compliance.
