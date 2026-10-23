-- AGO 065: restore independently authorized HUMAN operational and QA review.
-- Founder authorizes project strategy, market opportunities and exact
-- original founder-backed stage-scope decisions. The AI CEO continues to
-- attest ONLY bounded already-approved project work via its separate service.
-- Human operational review, constitutional attestations, calendar integrity
-- and independent QA remain independent of the submitting human founder.
--
-- This additive grant repairs 062's blanket reviewer revocation. Every
-- approval remains tenant-scoped, credential-backed, active-human verified
-- and audited by the Governance repository. No historical row is changed.
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT DISTINCT u.tenant_id,'reviewer',p.permission
FROM ago_users u
JOIN ago_user_roles r ON r.tenant_id=u.tenant_id
  AND r.user_id=u.id AND r.role='reviewer'
JOIN ago_employees e ON e.tenant_id=u.tenant_id
  AND e.id=u.id AND e.kind='human'
CROSS JOIN (VALUES ('approval:decide'),('qa:review')) AS p(permission)
WHERE u.active
ON CONFLICT DO NOTHING;

-- No AI, title-based or requester-controlled privilege grants;
-- ordinary new reviewers must be explicitly provisioned as signed human
-- users through ago.provision.add_reviewer. No delete or historical rewrite.
