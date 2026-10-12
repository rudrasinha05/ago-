ALTER TABLE ago_integration_settings DROP CONSTRAINT ago_integration_settings_kind_check;
ALTER TABLE ago_integration_settings ADD CONSTRAINT ago_integration_settings_kind_check CHECK(kind IN ('client','webhook','plugin','version','github_project','github_operation'));
CREATE TABLE ago_github_dispatch (
 tenant_id uuid NOT NULL,operation_id uuid NOT NULL,proposal_id uuid NOT NULL,
 status text NOT NULL CHECK(status IN ('started','succeeded','uncertain')),
 result jsonb,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),completed_at timestamptz,
 PRIMARY KEY(tenant_id,operation_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id)
);
CREATE FUNCTION ago_enterprise_projection_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record; expected text; n integer;
BEGIN
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 expected:=CASE TG_TABLE_NAME WHEN 'ago_graph_versions' THEN 'graph' WHEN 'ago_behavior_records' THEN 'behavior'
 WHEN 'ago_analytics_settings' THEN 'analytics' ELSE 'integration' END;
 SELECT * INTO p FROM ago_enterprise_proposals WHERE tenant_id=NEW.tenant_id AND id=NEW.proposal_id;
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=p.approval_id;
 SELECT coalesce(max(revision),0) INTO n FROM ago_enterprise_applied WHERE tenant_id=NEW.tenant_id AND domain=expected;
 IF p.id IS NULL OR p.domain IS DISTINCT FROM expected OR p.base_revision<>n
 OR a.status IS DISTINCT FROM 'approved' OR a.reviewer_id IS NULL OR a.reviewer_id=p.actor_id
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
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['ago_graph_versions','ago_behavior_records','ago_analytics_settings','ago_integration_settings'] LOOP
 EXECUTE format('CREATE TRIGGER enterprise_projection_guard BEFORE INSERT ON %I FOR EACH ROW EXECUTE FUNCTION ago_enterprise_projection_guard()',t);
END LOOP;END $$;
