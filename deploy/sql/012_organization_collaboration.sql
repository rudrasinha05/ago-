-- M6 coordination, calendar and institutional knowledge. PostgreSQL 15+.
CREATE TABLE ago_handoffs (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 requester_id uuid NOT NULL,
 sender_department_id uuid NOT NULL,
 receiver_department_id uuid NOT NULL,
 assignee_id uuid NOT NULL,
 title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 250),
 brief text NOT NULL CHECK (length(trim(brief)) BETWEEN 1 AND 6000),
 operation_key text NOT NULL CHECK (length(operation_key) BETWEEN 1 AND 160),
 status text NOT NULL DEFAULT 'requested'
   CHECK (status IN ('requested','accepted','rejected','completed')),
 receiver_actor_id uuid,
 conclusion text,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,operation_key),
 FOREIGN KEY (tenant_id,requester_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,sender_department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY (tenant_id,receiver_department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY (tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,receiver_actor_id) REFERENCES ago_users(tenant_id,id),
 CHECK (sender_department_id <> receiver_department_id),
 CHECK ((status='requested' AND receiver_actor_id IS NULL AND conclusion IS NULL)
     OR (status<>'requested' AND receiver_actor_id IS NOT NULL))
);
CREATE INDEX idx_ago_handoffs_inbox ON ago_handoffs(tenant_id,receiver_department_id,status);
CREATE TABLE ago_handoff_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 handoff_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 event text NOT NULL CHECK (event IN ('requested','accepted','rejected','completed')),
 note text NOT NULL CHECK (length(trim(note)) BETWEEN 1 AND 6000),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (tenant_id,handoff_id) REFERENCES ago_handoffs(tenant_id,id),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX idx_ago_handoff_events ON ago_handoff_events(tenant_id,handoff_id,created_at);
CREATE TRIGGER ago_handoff_events_protect BEFORE UPDATE OR DELETE ON ago_handoff_events
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_calendar_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 creator_id uuid NOT NULL,
 title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 250),
 detail text NOT NULL DEFAULT '',
 starts_at timestamptz NOT NULL,
 ends_at timestamptz NOT NULL,
 visibility text NOT NULL CHECK (visibility IN ('private','tenant')),
 status text NOT NULL DEFAULT 'scheduled'
   CHECK (status IN ('scheduled','cancelled')),
 operation_key text NOT NULL CHECK (length(operation_key) BETWEEN 1 AND 160),
 goal_id uuid,
 task_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,operation_key),
 FOREIGN KEY (tenant_id,creator_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,goal_id) REFERENCES ago_goals(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 CHECK (ends_at > starts_at)
);
CREATE INDEX idx_ago_calendar_range ON ago_calendar_events(tenant_id,starts_at,ends_at);
CREATE TABLE ago_calendar_attendees (
 tenant_id uuid NOT NULL,
 event_id uuid NOT NULL,
 employee_id uuid NOT NULL,
 response text NOT NULL DEFAULT 'invited'
   CHECK (response IN ('invited','accepted','declined')),
 PRIMARY KEY(tenant_id,event_id,employee_id),
 FOREIGN KEY (tenant_id,event_id) REFERENCES ago_calendar_events(tenant_id,id),
 FOREIGN KEY (tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id)
);

CREATE TABLE ago_knowledge_nodes (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 author_id uuid NOT NULL,
 kind text NOT NULL CHECK (kind IN ('fact','policy','artifact','decision')),
 label text NOT NULL CHECK (length(trim(label)) BETWEEN 1 AND 250),
 statement text NOT NULL CHECK (length(trim(statement)) BETWEEN 1 AND 12000),
 source_ref text NOT NULL CHECK (length(trim(source_ref)) BETWEEN 1 AND 1000),
 status text NOT NULL DEFAULT 'pending'
   CHECK (status IN ('pending','verified','rejected')),
 reviewer_id uuid,
 review_note text,
 created_at timestamptz NOT NULL DEFAULT now(),
 reviewed_at timestamptz,
 UNIQUE (tenant_id,id),
 FOREIGN KEY (tenant_id,author_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,reviewer_id) REFERENCES ago_users(tenant_id,id),
 CHECK (reviewer_id IS NULL OR reviewer_id <> author_id),
 CHECK ((status='pending' AND reviewer_id IS NULL AND reviewed_at IS NULL)
   OR (status<>'pending' AND reviewer_id IS NOT NULL AND reviewed_at IS NOT NULL
       AND length(trim(review_note)) > 0))
);
CREATE INDEX idx_ago_knowledge_review ON ago_knowledge_nodes(tenant_id,status,created_at);
CREATE TABLE ago_knowledge_edges (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 from_id uuid NOT NULL,
 to_id uuid NOT NULL,
 relation text NOT NULL CHECK (relation IN ('supports','contradicts','depends_on','references')),
 author_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,from_id,to_id,relation),
 FOREIGN KEY (tenant_id,from_id) REFERENCES ago_knowledge_nodes(tenant_id,id),
 FOREIGN KEY (tenant_id,to_id) REFERENCES ago_knowledge_nodes(tenant_id,id),
 FOREIGN KEY (tenant_id,author_id) REFERENCES ago_users(tenant_id,id),
 CHECK (from_id <> to_id)
);
CREATE TRIGGER ago_knowledge_edges_protect BEFORE UPDATE OR DELETE ON ago_knowledge_edges
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE OR REPLACE FUNCTION ago_guard_knowledge_review() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.status='pending'
   AND NEW.status IN ('verified','rejected')
   AND NEW.reviewed_at IS NOT NULL AND NEW.reviewer_id IS NOT NULL
   AND (OLD.id,OLD.tenant_id,OLD.author_id,OLD.kind,OLD.label,OLD.statement,
        OLD.source_ref,OLD.created_at) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.author_id,NEW.kind,NEW.label,NEW.statement,
        NEW.source_ref,NEW.created_at)
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Knowledge history cannot be rewritten';
END;
$$;
CREATE TRIGGER ago_knowledge_node_integrity BEFORE UPDATE OR DELETE ON ago_knowledge_nodes
 FOR EACH ROW EXECUTE FUNCTION ago_guard_knowledge_review();
