-- Hierarchical AI approval of project tasks (issue #8 M2).
-- The Founder approves the project (company level). Inside that approved
-- project, each task is approved by the lowest eligible AI in the worker's
-- hierarchy: the worker's direct manager, else the project manager, else the
-- AI CEO. That approver is recorded as RESPONSIBLE for the decision, together
-- with every higher-priority approver that was skipped and why.
CREATE TABLE ago_hierarchy_task_approvals (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 task_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 approver_id uuid NOT NULL,
 approver_level text NOT NULL CHECK (approver_level IN ('manager','project_manager','ceo')),
 worker_id uuid NOT NULL,
 skipped jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(skipped)='array'),
 founder_session_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,approver_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,worker_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,founder_session_id) REFERENCES ago_users(tenant_id,id),
 CHECK (approver_id <> worker_id)
);
CREATE INDEX ago_hierarchy_approvals_by_approver
 ON ago_hierarchy_task_approvals(tenant_id,approver_id,created_at DESC);
CREATE TRIGGER ago_hierarchy_task_approvals_immutable
 BEFORE UPDATE OR DELETE ON ago_hierarchy_task_approvals
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
