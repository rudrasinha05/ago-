-- PROJ-006: server-side stage continuation by the project's AI manager.
--
-- Until now only the discovery stage had a plan step, so a project stopped
-- after discovery passed QA: plan steps could not be added to an ACTIVE plan
-- and a founder intake stage could never be linked to a step afterwards.
--
-- This migration allows exactly two new, narrow transitions and records who
-- decided them. Nothing here approves, runs or releases anything: the new
-- step's task is created PROPOSED and still needs its own approval.

-- 1. Append-only record of every "previous stage passed QA -> next stage
--    opened" decision. decided_by_employee_id is the accountable AI manager;
--    authorized_by is the Founder whose signed session the server acted in.
CREATE TABLE ago_project_stage_progressions (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 plan_id uuid NOT NULL,
 from_stage text NOT NULL CHECK(from_stage IN ('discovery','architecture','implementation','quality')),
 to_stage text NOT NULL CHECK(to_stage IN ('architecture','implementation','quality','release')),
 passed_task_id uuid NOT NULL,
 plan_step_id uuid NOT NULL,
 task_id uuid NOT NULL,
 assignee_id uuid NOT NULL,
 decided_by_employee_id uuid NOT NULL,
 authorized_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,intake_id,to_stage),
 UNIQUE(tenant_id,task_id),
 FOREIGN KEY (tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,plan_id,plan_step_id) REFERENCES ago_plan_steps(tenant_id,plan_id,id),
 FOREIGN KEY (tenant_id,passed_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,decided_by_employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,authorized_by) REFERENCES ago_users(tenant_id,id),
 CHECK (passed_task_id <> task_id)
);
CREATE TRIGGER ago_project_stage_progressions_immutable
 BEFORE UPDATE OR DELETE ON ago_project_stage_progressions
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- 2. A recovery may now be decided by the AI manager (still inside a Founder
--    session, which stays in actor_id). NULL = the Founder decided it himself.
ALTER TABLE ago_plan_step_task_recoveries
 ADD COLUMN decided_by_employee_id uuid,
 ADD FOREIGN KEY (tenant_id,decided_by_employee_id) REFERENCES ago_employees(tenant_id,id);

-- 3. Same rules as 072, plus ONE new insert: on an ACTIVE plan, the step of
--    the NEXT founder-intake stage may be added when
--      * that stage has no step yet and the step takes its position,
--      * the step depends on the previous stage's step,
--      * the previous stage's task is completed and has a QA PASS verdict,
--      * the assignee is the stage's approved (activated) AI specialist.
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
 RAISE EXCEPTION 'Approved plans cannot be edited';
END;
$$;

-- 4. Founder intake stages stay append-only, except ONE link: a stage without
--    a step may be linked once to the step that was just added for it (same
--    plan, same position, active plan). No other column may change, a link can
--    never be moved or removed, and rows can never be deleted.
CREATE FUNCTION ago_guard_founder_intake_stage() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE'
   AND OLD.plan_step_id IS NULL AND NEW.plan_step_id IS NOT NULL
   AND (OLD.tenant_id,OLD.intake_id,OLD.plan_id,OLD.position,OLD.stage,
        OLD.deliverable,OLD.suggested_assignee_id) IS NOT DISTINCT FROM
       (NEW.tenant_id,NEW.intake_id,NEW.plan_id,NEW.position,NEW.stage,
        NEW.deliverable,NEW.suggested_assignee_id)
   AND EXISTS (SELECT 1 FROM ago_strategy_plans p
               WHERE p.tenant_id=NEW.tenant_id AND p.id=NEW.plan_id AND p.status='active')
   AND EXISTS (SELECT 1 FROM ago_plan_steps ps
               WHERE ps.tenant_id=NEW.tenant_id AND ps.plan_id=NEW.plan_id
                 AND ps.id=NEW.plan_step_id AND ps.position=NEW.position
                 AND ps.action='internal:brief') THEN
   RETURN NEW;
 END IF;
 RAISE EXCEPTION 'AGO audit/review history is append-only';
END;
$$;
DROP TRIGGER ago_founder_stages_append_only ON ago_founder_intake_stages;
CREATE TRIGGER ago_founder_stages_append_only
 BEFORE UPDATE OR DELETE ON ago_founder_intake_stages
 FOR EACH ROW EXECUTE FUNCTION ago_guard_founder_intake_stage();
