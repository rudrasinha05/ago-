-- Additive highest-policy authority. No existing grants or DNA are weakened.
CREATE TABLE ago_constitution_proposals (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 actor_id uuid NOT NULL, operation_key text NOT NULL, base_revision int NOT NULL CHECK(base_revision>=0),
 specification jsonb NOT NULL, simulation jsonb NOT NULL, digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 effective_at timestamptz NOT NULL, reviews jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,operation_key),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_constitution_adoptions (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, actor_id uuid NOT NULL,
 revision int NOT NULL CHECK(revision>0), blocked_contexts text[] NOT NULL,
 effective_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,revision), UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_constitution_proposals(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_constitution_emergencies (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id), actor_id uuid NOT NULL,
 operation_key text NOT NULL, blocked_contexts text[] NOT NULL CHECK(cardinality(blocked_contexts)>0),
 reason text NOT NULL, containment text NOT NULL, expires_at timestamptz NOT NULL,
 digest text NOT NULL, created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,operation_key),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '24 hours'),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_constitution_emergency_reviews (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, emergency_id uuid NOT NULL, actor_id uuid NOT NULL,
 postmortem text NOT NULL, recovery_evidence text NOT NULL, digest text NOT NULL, approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,emergency_id) REFERENCES ago_constitution_emergencies(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_constitution_emergency_closures (
 tenant_id uuid NOT NULL, emergency_id uuid NOT NULL, review_id uuid NOT NULL, actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(), PRIMARY KEY(tenant_id,emergency_id),
 FOREIGN KEY(tenant_id,emergency_id) REFERENCES ago_constitution_emergencies(tenant_id,id),
 FOREIGN KEY(tenant_id,review_id) REFERENCES ago_constitution_emergency_reviews(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_constitution_active ON ago_constitution_adoptions(tenant_id,revision DESC);
CREATE INDEX ago_constitution_emergency_active ON ago_constitution_emergencies(tenant_id,expires_at);
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['ago_constitution_proposals','ago_constitution_adoptions',
 'ago_constitution_emergencies','ago_constitution_emergency_reviews','ago_constitution_emergency_closures'] LOOP
 EXECUTE format('CREATE TRIGGER constitution_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only()',name);
 END LOOP;
END $$;
CREATE FUNCTION ago_constitution_adoption_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record; domain text; prior int;
BEGIN
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 SELECT * INTO p FROM ago_constitution_proposals WHERE tenant_id=NEW.tenant_id AND id=NEW.proposal_id;
 SELECT coalesce(max(revision),0) INTO prior FROM ago_constitution_adoptions WHERE tenant_id=NEW.tenant_id;
 IF NEW.actor_id IS DISTINCT FROM p.actor_id OR p.base_revision<>prior OR NEW.revision<>prior+1
 OR NEW.effective_at<p.effective_at
 OR to_jsonb(NEW.blocked_contexts) IS DISTINCT FROM p.specification->'blocked_contexts'
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=NEW.actor_id AND u.active AND e.kind='human' AND r.role='founder')
 THEN RAISE EXCEPTION 'Exact founder constitutional adoption required'; END IF;
 FOREACH domain IN ARRAY ARRAY['legal','security','architecture','audit','executive'] LOOP
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=(p.reviews->>domain)::uuid;
 IF a.status IS DISTINCT FROM 'approved' OR a.requester_id IS DISTINCT FROM p.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=p.actor_id OR NEW.effective_at<a.decided_at
 OR a.action IS DISTINCT FROM ('constitution:review:'||p.id::text||':'||domain||':'||p.digest)
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human')
 THEN RAISE EXCEPTION 'Independent five-domain constitutional review required'; END IF;
 END LOOP;
 RETURN NEW;
END $$;
CREATE TRIGGER constitution_adoption_guard BEFORE INSERT ON ago_constitution_adoptions
 FOR EACH ROW EXECUTE FUNCTION ago_constitution_adoption_guard();
CREATE FUNCTION ago_constitution_closure_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE r record; a record;
BEGIN
 SELECT * INTO r FROM ago_constitution_emergency_reviews WHERE tenant_id=NEW.tenant_id AND id=NEW.review_id;
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=r.approval_id;
 IF r.emergency_id IS DISTINCT FROM NEW.emergency_id OR r.actor_id IS DISTINCT FROM NEW.actor_id
 OR a.status IS DISTINCT FROM 'approved' OR a.requester_id IS DISTINCT FROM r.actor_id
 OR a.reviewer_id IS NULL OR a.reviewer_id=r.actor_id
 OR a.action IS DISTINCT FROM ('constitution:emergency-review:'||r.id::text||':'||r.digest)
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human')
 THEN RAISE EXCEPTION 'Independent exact post-incident review required'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER constitution_closure_guard BEFORE INSERT ON ago_constitution_emergency_closures
 FOR EACH ROW EXECUTE FUNCTION ago_constitution_closure_guard();
