-- QA FAIL rework (issue #8). 068 allowed one audited relink of a plan step
-- from a FAILED task. A task that finished but received an independent QA
-- FAIL verdict is equally unusable, so the same audited relink is allowed for
-- it. Everything else in 068 is unchanged: active plan, no running work, new
-- PROPOSED task with the same action and assignee, a matching append-only
-- recovery row, and no other column changes.
CREATE OR REPLACE FUNCTION ago_guard_plan_step() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE plan_state text;
BEGIN
 SELECT status INTO plan_state FROM ago_strategy_plans
 WHERE tenant_id=COALESCE(NEW.tenant_id,OLD.tenant_id)
   AND id=COALESCE(NEW.plan_id,OLD.plan_id);
 IF TG_OP='INSERT' AND plan_state='draft' THEN RETURN NEW; END IF;
 IF TG_OP='DELETE' AND plan_state='draft' THEN RETURN OLD; END IF;
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
