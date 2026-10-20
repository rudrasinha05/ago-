-- Founder sovereignty for operational decisions; preserve immutable audit trail.
-- Existing historical approvals remain unchanged.
DO $migration$
DECLARE constraint_name text;
BEGIN
  SELECT c.conname INTO constraint_name
  FROM pg_constraint c
  WHERE c.conrelid='ago_approval_requests'::regclass AND c.contype='c'
    AND pg_get_constraintdef(c.oid) ILIKE '%reviewer_id <> requester_id%'
  LIMIT 1;
  IF constraint_name IS NULL THEN
    RAISE EXCEPTION 'Expected historical self-decision check is missing';
  END IF;
  EXECUTE format('ALTER TABLE ago_approval_requests DROP CONSTRAINT %I',constraint_name);
END $migration$;
-- Authorization is enforced by current user/employee/founder role checks in
-- SecurityControls + ApprovalRepository, not by title or an AI-submitted role.
DELETE FROM ago_role_permissions WHERE permission='approval:decide' AND role<>'founder';
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT DISTINCT r.tenant_id,'founder','approval:decide'
FROM ago_user_roles r JOIN ago_users u ON u.tenant_id=r.tenant_id AND u.id=r.user_id
WHERE r.role='founder' AND u.active
ON CONFLICT DO NOTHING;
