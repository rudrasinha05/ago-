-- Sole-Founder companies (issue #8; DB side of 734d747): the Founder is the only human, so a
-- company-level enterprise change the Founder proposed may be approved by the
-- Founder. Same rules as 047, except reviewer = proposer is allowed ONLY when
-- that person is the active human Founder AND no other active human holds
-- approval:decide in the tenant. With another human approver, independence
-- is still required exactly as before.
-- True only when `actor` is the tenant's active human Founder and no OTHER
-- active human holds approval:decide (a sole-Founder company).
CREATE FUNCTION ago_sole_founder_self_review_ok(t uuid, actor uuid) RETURNS boolean
LANGUAGE sql STABLE AS $$
 SELECT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
   JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
   WHERE u.tenant_id=t AND u.id=actor AND u.active AND e.kind='human' AND r.role='founder')
 AND NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
   JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
   JOIN ago_role_permissions rp ON rp.tenant_id=r.tenant_id AND rp.role=r.role
   WHERE u.tenant_id=t AND u.id<>actor AND u.active AND e.kind='human'
     AND rp.permission='approval:decide')
$$;

CREATE OR REPLACE FUNCTION ago_enterprise_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record; expected text; n integer; self_review_ok boolean;
BEGIN
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 expected:=CASE TG_TABLE_NAME WHEN 'ago_graph_versions' THEN 'graph' WHEN 'ago_behavior_records' THEN 'behavior'
 WHEN 'ago_analytics_settings' THEN 'analytics' ELSE 'integration' END;
 SELECT * INTO p FROM ago_enterprise_proposals WHERE tenant_id=NEW.tenant_id AND id=NEW.proposal_id;
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=p.approval_id;
 SELECT coalesce(max(revision),0) INTO n FROM ago_enterprise_applied WHERE tenant_id=NEW.tenant_id AND domain=expected;
 self_review_ok := a.reviewer_id IS NOT NULL AND a.reviewer_id=p.actor_id
  AND ago_sole_founder_self_review_ok(NEW.tenant_id,p.actor_id);
 IF p.id IS NULL OR p.domain IS DISTINCT FROM expected OR p.base_revision<>n
 OR a.status IS DISTINCT FROM 'approved' OR a.reviewer_id IS NULL
 OR (a.reviewer_id=p.actor_id AND NOT self_review_ok)
 OR a.action IS DISTINCT FROM ('enterprise:review:'||p.domain||':'||p.id::text||':'||p.digest)
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=p.actor_id AND u.active AND e.kind='human' AND r.role='founder')
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 JOIN ago_role_permissions rp ON rp.tenant_id=r.tenant_id AND rp.role=r.role
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human' AND rp.permission='approval:decide')
 THEN RAISE EXCEPTION 'Current independently approved enterprise projection required'; END IF;
 IF TG_TABLE_NAME IN ('ago_analytics_settings','ago_integration_settings','ago_behavior_records') THEN
 IF NEW.kind IS DISTINCT FROM p.command OR NEW.payload IS DISTINCT FROM p.specification
 THEN RAISE EXCEPTION 'Projection differs from approved exact payload'; END IF;
 END IF;
 RETURN NEW;
END $$;

-- 042's apply guard: same rules, with the same single sole-Founder exception.
CREATE OR REPLACE FUNCTION ago_enterprise_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record;a record;n int;
BEGIN
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 IF TG_TABLE_NAME='ago_enterprise_proposals' THEN p:=NEW;
 ELSE SELECT * INTO p FROM ago_enterprise_proposals WHERE tenant_id=NEW.tenant_id AND id=NEW.proposal_id; END IF;
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=p.approval_id;
 SELECT coalesce(max(revision),0) INTO n FROM ago_enterprise_applied WHERE tenant_id=NEW.tenant_id AND domain=p.domain;
 IF p.id IS NULL OR NEW.actor_id IS DISTINCT FROM p.actor_id OR NEW.domain IS DISTINCT FROM p.domain
 OR a.requester_id IS DISTINCT FROM p.actor_id OR p.base_revision<>n
 OR a.action IS DISTINCT FROM ('enterprise:review:'||p.domain||':'||p.id::text||':'||p.digest)
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=NEW.actor_id AND u.active AND e.kind='human' AND r.role='founder')
 THEN RAISE EXCEPTION 'Exact current human enterprise review required'; END IF;
 IF TG_TABLE_NAME='ago_enterprise_applied' THEN
 IF NEW.revision<>n+1 OR a.status IS DISTINCT FROM 'approved' OR a.reviewer_id IS NULL
 OR (a.reviewer_id=p.actor_id AND NOT ago_sole_founder_self_review_ok(NEW.tenant_id,p.actor_id))
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 JOIN ago_role_permissions rp ON rp.tenant_id=r.tenant_id AND rp.role=r.role
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human' AND rp.permission='approval:decide')
 THEN RAISE EXCEPTION 'Independent current enterprise approval required'; END IF;
 ELSIF a.status IS DISTINCT FROM 'pending' THEN RAISE EXCEPTION 'Pending enterprise approval required'; END IF;
 RETURN NEW;
END $$;
