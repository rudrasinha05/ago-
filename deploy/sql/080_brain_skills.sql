-- SKL-002/003/005: a company's own Brain skills, skill gaps and skill use.
-- A skill is guidance text only: it never grants a permission, tool or approval.
-- Company skills are drafted by one AI employee and decided by another (the
-- AI CEO); the decision and both model names are kept. Rows are append-only:
-- a skill is never edited, only retired (and possibly restored) by the Founder.

CREATE TABLE ago_brain_skills (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 slug text NOT NULL CHECK(length(slug) <= 80 AND slug ~ '^[a-z0-9]+([.-][a-z0-9]+)*$'),
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 3 AND 120),
 domain text NOT NULL CHECK(length(domain) <= 60 AND domain ~ '^[a-z0-9]+([.-][a-z0-9]+)*$'),
 roles text[] NOT NULL CHECK(cardinality(roles) BETWEEN 1 AND 9),
 stages text[] NOT NULL CHECK(cardinality(stages) BETWEEN 1 AND 5),
 keywords text[] NOT NULL CHECK(cardinality(keywords) BETWEEN 1 AND 30),
 body text NOT NULL CHECK(length(body) BETWEEN 80 AND 900),
 source text NOT NULL CHECK(length(source) BETWEEN 3 AND 200),
 topic text NOT NULL CHECK(length(trim(topic)) BETWEEN 3 AND 500),
 status text NOT NULL CHECK(status IN ('approved','denied')),
 drafted_by uuid NOT NULL,
 reviewed_by uuid NOT NULL,
 draft_model text NOT NULL CHECK(length(draft_model) BETWEEN 1 AND 200),
 review_model text NOT NULL CHECK(length(review_model) BETWEEN 1 AND 200),
 review_text text NOT NULL CHECK(length(review_text) BETWEEN 1 AND 2000),
 requested_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,drafted_by) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,reviewed_by) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,requested_by) REFERENCES ago_users(tenant_id,id),
 CHECK(drafted_by <> reviewed_by)
);
CREATE UNIQUE INDEX ago_brain_skills_live ON ago_brain_skills(tenant_id,slug) WHERE status='approved';
CREATE INDEX ago_brain_skills_recent ON ago_brain_skills(tenant_id,created_at DESC);

CREATE FUNCTION ago_guard_brain_skill() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Brain skills are append-only; retire a skill instead of changing it';
END $$;
CREATE TRIGGER ago_brain_skills_guard BEFORE UPDATE OR DELETE ON ago_brain_skills
 FOR EACH ROW EXECUTE FUNCTION ago_guard_brain_skill();

-- Founder retirements of built-in ('ago:') or company ('co:') skills.
CREATE TABLE ago_brain_skill_retired (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 skill_ref text NOT NULL CHECK(length(skill_ref) <= 90 AND skill_ref ~ '^(ago|co):[a-z0-9]+([.-][a-z0-9]+)*$'),
 retired_by uuid NOT NULL,
 retired_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,skill_ref),
 FOREIGN KEY(tenant_id,retired_by) REFERENCES ago_users(tenant_id,id)
);

-- Which skills went into which task's prompt, by role (outcome comes from QA).
CREATE TABLE ago_brain_skill_uses (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 task_id uuid NOT NULL,
 skill_ref text NOT NULL CHECK(length(skill_ref) <= 90 AND skill_ref ~ '^(ago|co):[a-z0-9]+([.-][a-z0-9]+)*$'),
 role text NOT NULL CHECK(role IN ('ceo','cto','finance','risk','quality','pm','employee','qa','chat')),
 stage text,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 PRIMARY KEY(tenant_id,task_id,skill_ref,role),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id)
);
CREATE INDEX ago_brain_skill_uses_ref ON ago_brain_skill_uses(tenant_id,skill_ref);

-- Work that found no matching skill; the Founder can have the Brain learn it.
CREATE TABLE ago_brain_skill_gaps (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 task_id uuid NOT NULL,
 role text NOT NULL CHECK(role IN ('ceo','cto','finance','risk','quality','pm','employee','qa','chat')),
 stage text,
 topic text NOT NULL CHECK(length(trim(topic)) BETWEEN 3 AND 500),
 resolved_skill_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 resolved_at timestamptz,
 UNIQUE(tenant_id,task_id,role),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,resolved_skill_id) REFERENCES ago_brain_skills(tenant_id,id),
 CHECK((resolved_skill_id IS NULL)=(resolved_at IS NULL))
);

CREATE FUNCTION ago_guard_brain_skill_gap() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE' AND OLD.resolved_skill_id IS NULL AND NEW.resolved_skill_id IS NOT NULL
    AND (to_jsonb(OLD)-'resolved_skill_id'-'resolved_at')=(to_jsonb(NEW)-'resolved_skill_id'-'resolved_at') THEN
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'A skill gap is only ever resolved once';
END $$;
CREATE TRIGGER ago_brain_skill_gaps_guard BEFORE UPDATE OR DELETE ON ago_brain_skill_gaps
 FOR EACH ROW EXECUTE FUNCTION ago_guard_brain_skill_gap();
