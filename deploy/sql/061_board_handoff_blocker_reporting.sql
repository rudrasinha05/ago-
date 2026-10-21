-- Preserve immutable history while making future AI Board DENY reports truthful.
-- A completed Ollama invocation can still represent a FAILED governed delivery task.
-- No direct approval, publishing, hiring or Board RBAC is granted here.
CREATE OR REPLACE FUNCTION ago_company_agent_reporting()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE supervisor uuid; employee_name text; report_kind text; safe_detail text;
        board_hold boolean;
BEGIN
 IF OLD.status IS NOT DISTINCT FROM NEW.status
    OR NEW.status NOT IN ('completed','failed') THEN
  RETURN NEW;
 END IF;
 SELECT e.manager_id,e.name INTO supervisor,employee_name
 FROM ago_employees e
 WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.agent_id AND e.kind='ai';
 IF employee_name IS NULL THEN RETURN NEW; END IF;
 IF supervisor IS NULL THEN
  SELECT e.id INTO supervisor FROM ago_employees e
  JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id
  JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id
  WHERE e.tenant_id=NEW.tenant_id AND r.role='founder'
    AND e.kind='human' AND u.active ORDER BY e.id LIMIT 1;
 END IF;
 IF supervisor IS NULL OR supervisor=NEW.agent_id THEN RETURN NEW; END IF;
 board_hold:=COALESCE(NEW.result @> '{"board_blocked":true}'::jsonb, false);
 report_kind:=CASE
   WHEN NEW.status='completed' AND NOT board_hold THEN 'module_complete'
   ELSE 'blocker' END;
 safe_detail:=CASE
   WHEN board_hold
    THEN 'AI Board review paused the local handoff; downstream work did not run. Founder must inspect the persisted review evidence.'
   WHEN NEW.status='completed'
    THEN 'Approved AI task handler completed; independent human QA is still required.'
   ELSE 'Approved AI task handler failed; immediate manager should inspect the safe run record.'
 END;
 INSERT INTO ago_company_reports
  (tenant_id,author_id,recipient_id,kind,body,task_id,operation_key)
 VALUES (NEW.tenant_id,NEW.agent_id,supervisor,report_kind,safe_detail,NEW.task_id,NEW.id);
 INSERT INTO ago_company_chat
  (tenant_id,channel,author_name,body,kind,employee_id,task_id)
 VALUES (NEW.tenant_id,'employee:' || NEW.agent_id,employee_name,
   'AI employee reported ' || report_kind || ' to immediate superior',
   'report',NEW.agent_id,NEW.task_id);
 RETURN NEW;
END $$;
