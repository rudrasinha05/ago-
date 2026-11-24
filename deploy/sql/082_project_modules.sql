-- PROJ-014 / PROJ-016: prototype + integration delivery.
--
-- A project's implementation is a sequence of units: unit 0 is the working
-- prototype, units 1..n are the modules of the Founder-approved module plan.
-- Each unit is written, tested together with everything integrated before it
-- (complete regression in offline Docker), reviewed by independent QA and only
-- then integrated as a new immutable source version. The implementation stage
-- passes only after the last module is integrated, so a prototype alone never
-- completes a project.

CREATE TABLE ago_project_module_plans (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 project_id uuid NOT NULL,
 source text NOT NULL CHECK(source IN ('brief','architecture')),
 deferred text NOT NULL DEFAULT '' CHECK(length(deferred) <= 2000),
 status text NOT NULL DEFAULT 'proposed' CHECK(status IN ('proposed','approved')),
 decided_by uuid,
 decided_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,project_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id) ON DELETE CASCADE,
 CHECK((status='approved') = (decided_by IS NOT NULL AND decided_at IS NOT NULL))
);

CREATE TABLE ago_project_units (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 plan_id uuid NOT NULL,
 project_id uuid NOT NULL,
 position integer NOT NULL CHECK(position BETWEEN 0 AND 60),
 code text NOT NULL CHECK(code ~ '^(PROTOTYPE|M[0-9]{2,3})$'),
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 160),
 goal text NOT NULL CHECK(length(trim(goal)) BETWEEN 1 AND 600),
 status text NOT NULL DEFAULT 'planned' CHECK(status IN ('planned','in_progress','integrated')),
 base_version integer CHECK(base_version IS NULL OR base_version >= 0),
 started_at timestamptz,
 integrated_at timestamptz,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,plan_id,position),
 UNIQUE(tenant_id,plan_id,code),
 FOREIGN KEY(tenant_id,plan_id) REFERENCES ago_project_module_plans(tenant_id,id) ON DELETE CASCADE,
 CHECK((position = 0) = (code = 'PROTOTYPE')),
 CHECK(status = 'planned' OR (base_version IS NOT NULL AND started_at IS NOT NULL)),
 CHECK((status = 'integrated') = (integrated_at IS NOT NULL))
);
-- One unit at a time per project: the next starts only after the last is integrated.
CREATE UNIQUE INDEX ago_project_units_one_active ON ago_project_units(tenant_id,project_id)
 WHERE status='in_progress';

-- Integrated source of a project: each version is the complete file set after
-- one unit, tested together in offline Docker. Never edited or deleted.
CREATE TABLE ago_project_source_versions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 project_id uuid NOT NULL,
 version integer NOT NULL CHECK(version >= 1),
 unit_id uuid NOT NULL,
 task_id uuid NOT NULL,
 files jsonb NOT NULL CHECK(jsonb_typeof(files)='array' AND jsonb_array_length(files) BETWEEN 1 AND 400),
 files_sha256 text NOT NULL CHECK(files_sha256 ~ '^[0-9a-f]{64}$'),
 unittest_cases integer NOT NULL CHECK(unittest_cases >= 1),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,project_id,version),
 UNIQUE(tenant_id,unit_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id) ON DELETE CASCADE,
 FOREIGN KEY(tenant_id,unit_id) REFERENCES ago_project_units(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id)
);

CREATE FUNCTION ago_guard_project_source_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Project source versions are append-only';
END $$;
CREATE TRIGGER ago_project_source_versions_guard BEFORE UPDATE OR DELETE ON ago_project_source_versions
 FOR EACH ROW EXECUTE FUNCTION ago_guard_project_source_version();

-- A unit's definition never changes after the plan is approved; only its
-- progress moves forward (planned -> in_progress -> integrated).
CREATE FUNCTION ago_guard_project_unit() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION 'Project units are kept as evidence';
 END IF;
 IF NEW.id<>OLD.id OR NEW.tenant_id<>OLD.tenant_id OR NEW.plan_id<>OLD.plan_id
    OR NEW.project_id<>OLD.project_id OR NEW.position<>OLD.position OR NEW.code<>OLD.code
    OR NEW.title<>OLD.title OR NEW.goal<>OLD.goal THEN
  RAISE EXCEPTION 'A project unit definition cannot change';
 END IF;
 IF OLD.status='integrated' OR (OLD.status='in_progress' AND NEW.status='planned') THEN
  RAISE EXCEPTION 'Project unit progress only moves forward';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_project_units_guard BEFORE UPDATE OR DELETE ON ago_project_units
 FOR EACH ROW EXECUTE FUNCTION ago_guard_project_unit();

CREATE FUNCTION ago_guard_project_module_plan() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'DELETE' THEN
  RAISE EXCEPTION 'Module plans are kept as evidence';
 END IF;
 IF OLD.status='approved' OR NEW.id<>OLD.id OR NEW.project_id<>OLD.project_id
    OR NEW.source<>OLD.source OR NEW.deferred<>OLD.deferred THEN
  RAISE EXCEPTION 'An approved module plan cannot change';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_project_module_plans_guard BEFORE UPDATE OR DELETE ON ago_project_module_plans
 FOR EACH ROW EXECUTE FUNCTION ago_guard_project_module_plan();

-- The implementation step's task for each unit after the first: which unit it
-- builds and which integrated task it follows. Append-only audit.
CREATE TABLE ago_project_unit_tasks (
 id bigserial PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 unit_id uuid NOT NULL,
 plan_step_id uuid NOT NULL,
 previous_task_id uuid NOT NULL,
 task_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,task_id),
 UNIQUE(tenant_id,previous_task_id),
 FOREIGN KEY(tenant_id,unit_id) REFERENCES ago_project_units(tenant_id,id),
 FOREIGN KEY(tenant_id,previous_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id)
);
CREATE FUNCTION ago_guard_project_unit_task() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Project unit tasks are append-only';
END $$;
CREATE TRIGGER ago_project_unit_tasks_guard BEFORE UPDATE OR DELETE ON ago_project_unit_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_guard_project_unit_task();

CREATE OR REPLACE FUNCTION ago_guard_plan_step() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE plan_state text;
BEGIN
 SELECT status INTO plan_state FROM ago_strategy_plans
 WHERE tenant_id=COALESCE(NEW.tenant_id,OLD.tenant_id)
   AND id=COALESCE(NEW.plan_id,OLD.plan_id);
 IF TG_OP='INSERT' AND plan_state='draft' THEN RETURN NEW; END IF;
 IF TG_OP='DELETE' AND plan_state='draft' THEN RETURN OLD; END IF;
 IF TG_OP='INSERT' AND plan_state='active'
   AND NEW.task_id IS NULL AND NEW.action='internal:brief'
   AND NEW.position>1 AND NEW.depends_on IS NOT NULL
   AND EXISTS (
     SELECT 1
     FROM ago_founder_intake_stages s
     JOIN ago_founder_intake_stages prev ON prev.tenant_id=s.tenant_id
       AND prev.intake_id=s.intake_id AND prev.position=s.position-1
     JOIN ago_plan_steps pstep ON pstep.tenant_id=prev.tenant_id
       AND pstep.plan_id=prev.plan_id AND pstep.id=prev.plan_step_id
     JOIN ago_governed_tasks pt ON pt.tenant_id=pstep.tenant_id
       AND pt.id=pstep.task_id AND pt.status='completed'
     JOIN ago_task_reviews q ON q.tenant_id=pt.tenant_id
       AND q.task_id=pt.id AND q.verdict='pass'
     JOIN ago_project_stage_delegation_activations a ON a.tenant_id=s.tenant_id
       AND a.intake_id=s.intake_id AND a.stage=s.stage
     WHERE s.tenant_id=NEW.tenant_id AND s.plan_id=NEW.plan_id
       AND s.position=NEW.position AND s.plan_step_id IS NULL
       AND pstep.id=NEW.depends_on AND a.assignee_id=NEW.assignee_id
   ) THEN
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND plan_state='active'
   AND OLD.task_id IS NULL AND NEW.task_id IS NOT NULL
   AND (OLD.id,OLD.tenant_id,OLD.plan_id,OLD.position,OLD.action,
        OLD.assignee_id,OLD.depends_on) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.plan_id,NEW.position,NEW.action,
        NEW.assignee_id,NEW.depends_on) THEN
   RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND plan_state='active'
   AND OLD.task_id IS NOT NULL AND NEW.task_id IS NOT NULL
   AND OLD.task_id<>NEW.task_id
   AND (OLD.id,OLD.tenant_id,OLD.plan_id,OLD.position,OLD.action,
        OLD.assignee_id,OLD.depends_on) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.plan_id,NEW.position,NEW.action,
        NEW.assignee_id,NEW.depends_on)
   AND EXISTS (SELECT 1 FROM ago_governed_tasks t
               WHERE t.tenant_id=OLD.tenant_id AND t.id=OLD.task_id
                 AND (t.status='failed'
                      OR (t.status='completed' AND EXISTS (
                          SELECT 1 FROM ago_task_reviews q
                          WHERE q.tenant_id=t.tenant_id AND q.task_id=t.id
                            AND q.verdict='fail'))))
   AND NOT EXISTS (SELECT 1 FROM ago_agent_runs r
                   WHERE r.tenant_id=OLD.tenant_id AND r.task_id=OLD.task_id AND r.status='running')
   AND EXISTS (SELECT 1 FROM ago_governed_tasks n
               WHERE n.tenant_id=NEW.tenant_id AND n.id=NEW.task_id AND n.status='proposed'
                 AND n.action=OLD.action AND n.assignee_id=OLD.assignee_id)
   AND EXISTS (SELECT 1 FROM ago_plan_step_task_recoveries v
               WHERE v.tenant_id=OLD.tenant_id AND v.plan_id=OLD.plan_id
                 AND v.plan_step_id=OLD.id AND v.failed_task_id=OLD.task_id
                 AND v.recovery_task_id=NEW.task_id) THEN
   RETURN NEW;
 END IF;
 -- PROJ-014: after a unit passed tests and independent QA and was integrated,
 -- the implementation step moves on to the NEXT unit's proposed task. Allowed
 -- only with the audited unit-task record, from a completed QA-PASS task.
 IF TG_OP='UPDATE' AND plan_state='active'
   AND OLD.task_id IS NOT NULL AND NEW.task_id IS NOT NULL
   AND OLD.task_id<>NEW.task_id
   AND (OLD.id,OLD.tenant_id,OLD.plan_id,OLD.position,OLD.action,
        OLD.assignee_id,OLD.depends_on) IS NOT DISTINCT FROM
       (NEW.id,NEW.tenant_id,NEW.plan_id,NEW.position,NEW.action,
        NEW.assignee_id,NEW.depends_on)
   AND EXISTS (SELECT 1 FROM ago_governed_tasks t
               JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
                 AND q.verdict='pass'
               WHERE t.tenant_id=OLD.tenant_id AND t.id=OLD.task_id AND t.status='completed')
   AND EXISTS (SELECT 1 FROM ago_governed_tasks n
               WHERE n.tenant_id=NEW.tenant_id AND n.id=NEW.task_id AND n.status='proposed'
                 AND n.action=OLD.action AND n.assignee_id=OLD.assignee_id)
   AND EXISTS (SELECT 1 FROM ago_project_unit_tasks ut
               WHERE ut.tenant_id=OLD.tenant_id AND ut.plan_step_id=OLD.id
                 AND ut.previous_task_id=OLD.task_id AND ut.task_id=NEW.task_id) THEN
   RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Approved plans cannot be edited';
END;
$$;
