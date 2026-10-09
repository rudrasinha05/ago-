-- M5 economics, decision experiments and tenant scorecard inputs.
CREATE TABLE ago_credit_budgets (
 tenant_id uuid PRIMARY KEY REFERENCES ago_tenants(id) ON DELETE CASCADE,
 ceiling numeric(18,4) NOT NULL CHECK (ceiling >= 0),
 consumed numeric(18,4) NOT NULL DEFAULT 0 CHECK (consumed >= 0),
 updated_at timestamptz NOT NULL DEFAULT now(),
 CHECK (consumed <= ceiling)
);
CREATE TABLE ago_credit_usage (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 operation_key text NOT NULL CHECK (length(operation_key) BETWEEN 1 AND 180),
 amount numeric(18,4) NOT NULL CHECK (amount > 0),
 category text NOT NULL CHECK (length(category) BETWEEN 1 AND 100),
 actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,operation_key),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX idx_ago_credit_usage_tenant_time ON ago_credit_usage(tenant_id,created_at);
CREATE TRIGGER ago_credit_usage_protect BEFORE UPDATE OR DELETE ON ago_credit_usage
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_policy_experiments (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 proposer_id uuid NOT NULL,
 hypothesis text NOT NULL CHECK (length(trim(hypothesis)) BETWEEN 1 AND 2000),
 baseline text NOT NULL CHECK (length(trim(baseline)) BETWEEN 1 AND 2000),
 candidate text NOT NULL CHECK (length(trim(candidate)) BETWEEN 1 AND 2000),
 approval_id uuid UNIQUE,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE INDEX idx_ago_policy_experiments_tenant ON ago_policy_experiments(tenant_id,created_at);
