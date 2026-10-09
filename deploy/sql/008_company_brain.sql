-- M3 Company Brain: tenant-scoped goals, plans and forward-only plan dependency graph.
CREATE TABLE ago_goals (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 parent_id uuid,
 created_by uuid NOT NULL,
 title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 250),
 description text NOT NULL DEFAULT '',
 status text NOT NULL DEFAULT 'active' CHECK (status IN ('active','completed','cancelled')),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY (tenant_id,created_by) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,parent_id) REFERENCES ago_goals(tenant_id,id),
 CHECK (id <> parent_id)
);
CREATE INDEX idx_ago_goals_tenant_status ON ago_goals(tenant_id,status);

CREATE TABLE ago_strategy_plans (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 goal_id uuid NOT NULL,
 proposer_id uuid NOT NULL,
 title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 250),
 status text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','pending_approval','active','rejected')),
 approval_id uuid UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 activated_at timestamptz,
 UNIQUE(tenant_id,id),
 FOREIGN KEY (tenant_id,goal_id) REFERENCES ago_goals(tenant_id,id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status='draft' AND approval_id IS NULL) OR (status<>'draft' AND approval_id IS NOT NULL))
);
CREATE INDEX idx_ago_strategy_plans_tenant ON ago_strategy_plans(tenant_id,goal_id,status);

CREATE TABLE ago_plan_steps (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 plan_id uuid NOT NULL,
 position integer NOT NULL CHECK (position >= 1),
 action text NOT NULL CHECK (length(trim(action)) BETWEEN 1 AND 500),
 assignee_id uuid NOT NULL,
 depends_on uuid,
 task_id uuid,
 UNIQUE(tenant_id,plan_id,id),
 UNIQUE(tenant_id,plan_id,position),
 UNIQUE(tenant_id,task_id),
 FOREIGN KEY (tenant_id,plan_id) REFERENCES ago_strategy_plans(tenant_id,id),
 FOREIGN KEY (tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,plan_id,depends_on)
     REFERENCES ago_plan_steps(tenant_id,plan_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 CHECK (id <> depends_on)
);
CREATE INDEX idx_ago_plan_steps_tenant_plan ON ago_plan_steps(tenant_id,plan_id,position);
