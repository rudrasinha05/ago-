-- Reviewed temporal policy. Existing calendar events keep their append-oriented guard.
CREATE TABLE ago_calendar_proposals (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 actor_id uuid NOT NULL, approval_id uuid NOT NULL, operation_key text NOT NULL,
 base_revision int NOT NULL CHECK(base_revision>=0),
 command text NOT NULL CHECK(command IN ('policy','window','window_cancel','event_link','reschedule')),
 specification jsonb NOT NULL CHECK(jsonb_typeof(specification)='object'),
 source jsonb NOT NULL CHECK(jsonb_typeof(source)='object'),
 rationale text NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 6000),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,operation_key),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TABLE ago_calendar_changes (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL, proposal_id uuid NOT NULL, actor_id uuid NOT NULL,
 revision int NOT NULL CHECK(revision>0), result jsonb NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,revision), UNIQUE(tenant_id,proposal_id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_calendar_proposals(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_calendar_timing_audit (
 id uuid PRIMARY KEY, tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 operation_key text NOT NULL, kind text NOT NULL,
 detail jsonb NOT NULL CHECK(jsonb_typeof(detail)='object'),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(), UNIQUE(tenant_id,operation_key)
);
CREATE INDEX ago_calendar_changes_latest ON ago_calendar_changes(tenant_id,revision DESC);
CREATE INDEX ago_calendar_signals_latest ON ago_calendar_timing_audit(tenant_id,occurred_at DESC);
DO $$ DECLARE name text; BEGIN
 FOREACH name IN ARRAY ARRAY['ago_calendar_proposals','ago_calendar_changes','ago_calendar_timing_audit'] LOOP
 EXECUTE format('CREATE TRIGGER calendar_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only()',name);
 END LOOP;
END $$;
CREATE FUNCTION ago_calendar_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record; prior int;
BEGIN
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 IF TG_TABLE_NAME='ago_calendar_proposals' THEN p:=NEW;
 ELSE SELECT * INTO p FROM ago_calendar_proposals WHERE tenant_id=NEW.tenant_id AND id=NEW.proposal_id;
 END IF;
 SELECT * INTO a FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=p.approval_id;
 SELECT coalesce(max(revision),0) INTO prior FROM ago_calendar_changes WHERE tenant_id=NEW.tenant_id;
 IF p.id IS NULL OR NEW.actor_id IS DISTINCT FROM p.actor_id
 OR a.requester_id IS DISTINCT FROM p.actor_id
 OR a.action IS DISTINCT FROM ('calendar:review:'||p.id::text||':'||p.digest)
 OR p.base_revision<>prior
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 WHERE u.tenant_id=NEW.tenant_id AND u.id=NEW.actor_id AND u.active AND e.kind='human' AND r.role='founder')
 THEN RAISE EXCEPTION 'Exact current human-authored calendar package required'; END IF;
 IF TG_TABLE_NAME='ago_calendar_changes' THEN
 IF NEW.revision<>prior+1 OR a.status IS DISTINCT FROM 'approved'
 OR a.reviewer_id IS NULL OR a.reviewer_id=p.actor_id
 OR NOT EXISTS(SELECT 1 FROM ago_users u JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
 JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
 JOIN ago_role_permissions rp ON rp.tenant_id=r.tenant_id AND rp.role=r.role
 WHERE u.tenant_id=NEW.tenant_id AND u.id=a.reviewer_id AND u.active AND e.kind='human' AND rp.permission='approval:decide')
 THEN RAISE EXCEPTION 'Independent active exact calendar review required'; END IF;
 ELSE
 IF a.status IS DISTINCT FROM 'pending' THEN RAISE EXCEPTION 'New pending calendar approval required'; END IF;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER calendar_proposal_guard BEFORE INSERT ON ago_calendar_proposals
 FOR EACH ROW EXECUTE FUNCTION ago_calendar_review_guard();
CREATE TRIGGER calendar_change_guard BEFORE INSERT ON ago_calendar_changes
 FOR EACH ROW EXECUTE FUNCTION ago_calendar_review_guard();
