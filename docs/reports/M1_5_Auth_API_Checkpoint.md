# M1.5 — Authentication API Checkpoint

Added opt-in FastAPI authentication router `build_auth_router` with typed login requests and short-lived signed access tokens. The router is intentionally **not** mounted in the main application. It requires an identity backend, token signer, and trusted tenant validation.

Security boundaries:
- A production deployment must implement per-account/IP rate limiting, audit events, trusted tenant routing, TLS, MFA, session revocation, key rotation, and account recovery.
- No user enumeration details are exposed in login errors.
- Current custom tokens are not OIDC/JWT. No refresh token support.
- This is a foundation and is not safe to expose publicly without security review.
