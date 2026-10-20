-- AGO founder command center: explicit role accountability, board seats and upward reports.
-- No elevation of RBAC or autonomous execution from a board label.
ALTER TABLE ago_employees
  ADD COLUMN role_title text NOT NULL DEFAULT '' CHECK (length(role_title) <= 150),
  ADD COLUMN core_responsibilities text NOT NULL DEFAULT '' CHECK (length(core_responsibilities) <= 3000),
  ADD COLUMN extra_responsibilities text NOT NULL DEFAULT '' CHECK (length(extra_responsibilities) <= 3000);

CREATE TABLE ago_company_board_appointments (
  tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
  seat text NOT NULL CHECK (seat IN (
    'Strategy & Vision','Technology Oversight','Finance & Budget',
    'Risk & Compliance','Quality & Release'
  )),
  employee_id uuid NOT NULL,
  appointed_by uuid NOT NULL,
  appointed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,seat),
  UNIQUE (tenant_id,employee_id),
  FOREIGN KEY (tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,appointed_by) REFERENCES ago_users(tenant_id,id)
);

CREATE TABLE ago_company_reports (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
  author_id uuid NOT NULL,
  recipient_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('doubt','blocker','module_complete','phase_complete')),
  body text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 6000),
  task_id uuid,
  operation_key uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,author_id,operation_key),
  FOREIGN KEY (tenant_id,author_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,recipient_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
  CHECK (author_id <> recipient_id)
);
CREATE INDEX ago_company_reports_inbox ON ago_company_reports(tenant_id,recipient_id,id DESC);
CREATE INDEX ago_company_reports_outbox ON ago_company_reports(tenant_id,author_id,id DESC);

-- Readable work events participate in the established durable company timeline.
ALTER TABLE ago_company_chat DROP CONSTRAINT ago_company_chat_kind_check;
ALTER TABLE ago_company_chat ADD CONSTRAINT ago_company_chat_kind_check
  CHECK(kind IN ('message','status','staffing','report','github','qa','docs'));

-- Disallow modifying historical reporting evidence, including deletion.
CREATE TRIGGER ago_company_reports_append_only BEFORE UPDATE OR DELETE ON ago_company_reports
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- Independent QA decisions generate durable notifications for both reviewer and author.
CREATE FUNCTION ago_company_qa_event() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 INSERT INTO ago_company_chat
  (tenant_id,channel,author_name,body,kind,employee_id,task_id)
 SELECT NEW.tenant_id,'employee:' || e.id,e.name,
  'Independent QA ' || NEW.verdict || ' recorded on assigned task','qa',e.id,NEW.task_id
 FROM ago_employees e
 WHERE e.tenant_id=NEW.tenant_id AND e.id IN (NEW.author_id,NEW.reviewer_id);
 RETURN NEW;
END $$;
CREATE TRIGGER ago_company_qa_event AFTER INSERT ON ago_task_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_company_qa_event();

-- An actually executed AI handler automatically reports its finished state to its
-- immediate manager, or to the founder when at department root. No model-authored
-- secret content is copied into a shared timeline.
CREATE FUNCTION ago_company_agent_reporting() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE supervisor uuid; employee_name text; report_kind text; safe_detail text;
BEGIN
 IF OLD.status IS NOT DISTINCT FROM NEW.status OR NEW.status NOT IN ('completed','failed') THEN
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
 report_kind:=CASE WHEN NEW.status='completed' THEN 'module_complete' ELSE 'blocker' END;
 safe_detail:=CASE WHEN NEW.status='completed'
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
CREATE TRIGGER ago_company_agent_reporting AFTER UPDATE ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_company_agent_reporting();
