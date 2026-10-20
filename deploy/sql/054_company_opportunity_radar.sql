-- Tenant-isolated durable opportunity suggestions. They are hypotheses, not sales.
CREATE TABLE ago_company_opportunities (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 cycle_start date NOT NULL,
 catalog_key text NOT NULL CHECK(length(catalog_key) BETWEEN 3 AND 80),
 title text NOT NULL CHECK(length(title) BETWEEN 10 AND 220),
 target_customer text NOT NULL,
 customer_problem text NOT NULL,
 proposed_offer text NOT NULL,
 revenue_path text NOT NULL,
 validation_next_step text NOT NULL,
 accountable_manager_id uuid NOT NULL,
 assignment_source text NOT NULL
   CHECK(assignment_source IN ('executive_manager','founder_escalation')),
 discovery_type text NOT NULL DEFAULT 'catalog_hypothesis'
   CHECK(discovery_type='catalog_hypothesis'),
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,cycle_start,catalog_key),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,accountable_manager_id)
   REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(approval_id) REFERENCES ago_approval_requests(id)
);
CREATE INDEX ago_company_opportunity_time
 ON ago_company_opportunities(tenant_id,created_at DESC);
-- A founder-approved hypothesis is permission to investigate and plan,
-- not permission to send unsolicited mail, spend money or ship a product.
