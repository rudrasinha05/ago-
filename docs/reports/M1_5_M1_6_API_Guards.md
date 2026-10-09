# M1.5/M1.6 — API Authorization Guards

Added reusable FastAPI bearer-token verification and tenant-scoped permission dependencies. Routes explicitly opt in; the main app remains unchanged. Unit tests cover missing/invalid tokens, permitted access and cross-tenant denial.

**Security warning:** The sample test resolves tenant IDs from route path parameters for demonstration. In production, tenant ownership must be resolved from trusted server-side resource records; never treat a client-supplied tenant as authoritative. Production hardening still requires persisted policy configuration, session revocation, rate limits, auditing, key rotation and real database integration.
