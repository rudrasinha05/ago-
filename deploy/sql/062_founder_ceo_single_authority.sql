-- Founder remains the only human business approver, regardless of other users.
-- Migrate forward: preserve all earlier immutable approvals and audit history.
DELETE FROM ago_role_permissions WHERE permission='approval:decide' AND role<>'founder';
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT DISTINCT r.tenant_id,'founder','approval:decide'
FROM ago_user_roles r JOIN ago_users u ON u.tenant_id=r.tenant_id AND u.id=r.user_id
WHERE r.role='founder' AND u.active
ON CONFLICT DO NOTHING;
-- CEO has no generic auth role or token. Scoped project decisions are
-- controlled by an independently auditable verified project-work gate.
