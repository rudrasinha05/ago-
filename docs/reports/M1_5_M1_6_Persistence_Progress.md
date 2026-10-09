# M1.5 / M1.6 — Persistent Identity and Authorization

Implemented on develop:
- PostgreSQL tenant/user/role schema in migration 002.
- Composite tenant/user foreign key prevents cross-tenant role assignments.
- Identity repository for tenant creation, user creation, credential verification, role assignment and deactivation.
- Access service that verifies active user status and reloads role assignments from the database before authorizing.
- Cross-tenant deny-by-default checks and unit tests.

Security boundaries:
- No public authentication endpoints or password-reset flow.
- No MFA, token/session revocation, throttling, audit trail, OIDC integration or database row-level security.
- Role permission policy is in-memory; permissions must be configured by trusted application code.
- Password hash uses PBKDF2; security review should consider Argon2id and production credential policies.
- SQL migration and database adapter need real PostgreSQL integration tests.
- The user deactivation mechanism does not independently revoke stateless tokens, but the AccessService checks the active flag at authorization time.
- M1.5/M1.6 remain in progress and are not production ready.
