CREATE TABLE ago_enterprise_proposals (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 domain text NOT NULL CHECK(domain IN ('graph','behavior','analytics','integration')),
 actor_id uuid NOT NULL, approval_id uuid NOT NULL, operation_key text NOT NULL,
 base_revision int NOT NULL CHECK(base_revision>=0), command text NOT NULL,
 specification jsonb NOT NULL, source jsonb NOT NULL, rationale text NOT NULL,
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'), created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,domain,operation_key),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TABLE ago_enterprise_applied (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,domain text NOT NULL,proposal_id uuid NOT NULL,
 actor_id uuid NOT NULL,revision int NOT NULL CHECK(revision>0),result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),UNIQUE(tenant_id,domain,revision),UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX enterprise_review_domain ON ago_enterprise_proposals(tenant_id,domain,created_at DESC);
CREATE FUNCTION ago_enterprise_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
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
 IF NEW.revision<>n+1 OR a.status IS DISTINCT FROM 'approved' OR a.reviewer_id IS NULL OR a.reviewer_id=p.actor_id
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 JOIN ago_role_permissions rp ON rp.tenant_id=r.tenant_id AND rp.role=r.role
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human' AND rp.permission='approval:decide')
 THEN RAISE EXCEPTION 'Independent current enterprise approval required'; END IF;
 ELSIF a.status IS DISTINCT FROM 'pending' THEN RAISE EXCEPTION 'Pending enterprise approval required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER enterprise_proposal_guard BEFORE INSERT ON ago_enterprise_proposals FOR EACH ROW EXECUTE FUNCTION ago_enterprise_review_guard();
CREATE TRIGGER enterprise_applied_guard BEFORE INSERT ON ago_enterprise_applied FOR EACH ROW EXECUTE FUNCTION ago_enterprise_review_guard();
CREATE TRIGGER enterprise_proposal_immutable BEFORE UPDATE OR DELETE ON ago_enterprise_proposals FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER enterprise_applied_immutable BEFORE UPDATE OR DELETE ON ago_enterprise_applied FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
