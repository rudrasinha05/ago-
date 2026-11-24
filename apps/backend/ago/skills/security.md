# Security skills

## sec.secure-coding
title: Secure coding checklist
roles: employee, cto, risk, qa
stages: implementation, quality
keywords: security, secure, vulnerability, injection, xss, owasp, validation, sanitize
source: AGO original (Claude, 2026-11-24)
---
1. Validate every input by type, length and allowed values. 2. Parameterized queries; escape output for HTML. 3. Authenticate every request; authorize every object (tenant, owner). 4. Secrets from a secret store; never in code, logs or URLs. 5. Hash passwords with a slow algorithm (argon2/bcrypt). 6. Least privilege for services and tokens. 7. Dependencies scanned; errors never expose internals.

## sec.threat-model
title: Threat model a feature
roles: risk, cto
stages: architecture
keywords: threat, risk, attack, security, abuse, model, stride
source: AGO original (Claude, 2026-11-24)
---
1. Draw the data flow and trust boundaries. 2. For each boundary ask STRIDE: spoofing, tampering, repudiation, information disclosure, denial of service, elevation of privilege. 3. Rate each threat by likelihood and impact. 4. Pick mitigations for the high ones. 5. Note what is accepted risk and who accepted it. 6. Add tests or checks for each mitigation. 7. Revisit when the design changes.

## sec.privacy-data
title: Personal data and privacy
roles: risk, employee, cto
stages: architecture, implementation
keywords: privacy, personal, data, pii, gdpr, dpdp, consent, retention, user, data, protection
source: AGO original (Claude, 2026-11-24)
---
1. Collect only data you need for a stated purpose. 2. Tell users what and why in plain words; get consent where required (GDPR, India DPDP Act). 3. Encrypt in transit and at rest. 4. Limit who can read it; log access. 5. Set retention periods and delete on time. 6. Let users see, correct and delete their data. 7. Plan breach notification steps.

## sec.auth
title: Login, sessions and access control
roles: employee, cto, risk
stages: architecture, implementation
keywords: login, authentication, auth, session, password, token, jwt, role, permission, mfa
source: AGO original (Claude, 2026-11-24)
---
1. Use a proven library or provider; do not invent crypto. 2. Rate-limit login; lock or slow after failures. 3. Offer MFA for admins. 4. Short-lived sessions, rotate tokens, revoke on logout and password change. 5. Role and resource checks on the server, never only in the UI. 6. Secure cookies (HttpOnly, Secure, SameSite). 7. Log security events without secrets.
