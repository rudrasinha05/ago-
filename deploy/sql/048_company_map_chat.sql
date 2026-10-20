-- Durable organization conversation and transaction-bound task status timeline.
CREATE TABLE ago_company_chat (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 channel text NOT NULL,
 author_id uuid,
 author_name text NOT NULL,
 body text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 20000),
 reply_to bigint REFERENCES ago_company_chat(id),
 operation_key uuid,
 kind text NOT NULL DEFAULT 'message' CHECK (kind IN ('message','status','staffing')),
 employee_id uuid,
 task_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,author_id,operation_key),
 FOREIGN KEY (tenant_id,author_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id)
);
CREATE INDEX ago_company_chat_timeline ON ago_company_chat(tenant_id,id DESC);
CREATE INDEX ago_company_chat_channel ON ago_company_chat(tenant_id,channel,id DESC);
CREATE FUNCTION ago_company_task_status() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP = 'INSERT' OR NEW.status IS DISTINCT FROM OLD.status THEN
  INSERT INTO ago_company_chat(tenant_id,channel,author_name,body,kind,employee_id,task_id)
  SELECT NEW.tenant_id,'employee:' || e.id,e.name,
   NEW.action || ' → ' || NEW.status,'status',e.id,NEW.id
  FROM ago_employees e WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id;
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_company_task_status AFTER INSERT OR UPDATE ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_company_task_status();
-- Existing tasks contribute a labelled snapshot, never invented historical transitions.
INSERT INTO ago_company_chat(tenant_id,channel,author_name,body,kind,employee_id,task_id,created_at)
SELECT t.tenant_id,'employee:' || e.id,e.name,
 'Initial task snapshot: ' || t.action || ' → ' || t.status,'status',e.id,t.id,now()
FROM ago_governed_tasks t JOIN ago_employees e ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id;
