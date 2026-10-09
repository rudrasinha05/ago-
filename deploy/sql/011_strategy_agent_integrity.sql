-- M3–M5 tamper-resistance: immutable submitted plans, terminal runs and experiments.
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
 RAISE EXCEPTION 'Approved plans cannot be edited';
END;
$$;
CREATE TRIGGER ago_plan_steps_integrity
 BEFORE INSERT OR UPDATE OR DELETE ON ago_plan_steps
 FOR EACH ROW EXECUTE FUNCTION ago_guard_plan_step();

CREATE OR REPLACE FUNCTION ago_guard_agent_run() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE'
  AND OLD.status='running' AND NEW.status IN ('completed','failed')
  AND NEW.finished_at IS NOT NULL
  AND (OLD.id,OLD.tenant_id,OLD.task_id,OLD.agent_id,
       OLD.executor_id,OLD.started_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.task_id,NEW.agent_id,
       NEW.executor_id,NEW.started_at)
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Agent run history cannot be rewritten';
END;
$$;
CREATE TRIGGER ago_agent_run_integrity
 BEFORE UPDATE OR DELETE ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_guard_agent_run();
CREATE TRIGGER ago_policy_experiment_protect
 BEFORE UPDATE OR DELETE ON ago_policy_experiments
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
