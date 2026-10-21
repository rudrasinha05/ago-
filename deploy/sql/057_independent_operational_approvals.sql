-- Reconcile founder sovereignty with independent operational review.
-- Strategic company opportunities and founder project plans remain founder-only,
-- enforced by authenticated GovernanceGate and ApprovalRepository.
-- Existing independent technical review must NOT be silently removed.
-- No generic role elevation: only already-provisioned human reviewer roles
-- receive operational approval rights. The founder has separate strategic rights.
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT DISTINCT r.tenant_id,'reviewer','approval:decide'
FROM ago_user_roles r
JOIN ago_users u ON u.tenant_id=r.tenant_id AND u.id=r.user_id AND u.active
JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
WHERE r.role='reviewer'
ON CONFLICT DO NOTHING;

-- Existing reviewer approval permissions are not automatically converted into
-- founder strategic authority. Historical append-only approval/audit records
-- and the authorizer's real identity are preserved.
