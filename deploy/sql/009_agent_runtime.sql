-- M4 governed AI workforce: one persistent agent run per approved task.
CREATE TABLE ago_agent_runs (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 agent_id uuid NOT NULL,
 executor_id uuid NOT NULL,
 status text NOT NULL CHECK (status IN ('running','completed','failed')),
 result jsonb,
 failure_code text,
 started_at timestamptz NOT NULL DEFAULT now(),
 finished_at timestamptz,
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,task_id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,agent_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,executor_id) REFERENCES ago_users(tenant_id,id),
 CHECK (
   (status='running' AND finished_at IS NULL AND failure_code IS NULL)
   OR (status IN ('completed','failed') AND finished_at IS NOT NULL)
 )
);
CREATE INDEX idx_ago_agent_runs_tenant_status
 ON ago_agent_runs(tenant_id,status,started_at DESC);
CREATE TABLE ago_agent_messages (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 run_id uuid NOT NULL,
 kind text NOT NULL CHECK (kind IN ('input','output','evidence')),
 content text NOT NULL CHECK (length(content) BETWEEN 1 AND 20000),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (tenant_id,run_id) REFERENCES ago_agent_runs(tenant_id,id)
);
CREATE INDEX idx_ago_agent_messages_run ON ago_agent_messages(tenant_id,run_id,created_at);
CREATE TRIGGER ago_agent_messages_protect
 BEFORE UPDATE OR DELETE ON ago_agent_messages
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
