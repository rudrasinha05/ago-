CREATE TABLE ago_behavior_records (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),employee_id uuid,
 kind text NOT NULL CHECK(kind IN ('definition','observation','decision','resolve_appeal')),
 payload jsonb NOT NULL,source jsonb NOT NULL,proposal_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id)
);
CREATE INDEX behavior_employee_history ON ago_behavior_records(tenant_id,employee_id,created_at);
CREATE TABLE ago_behavior_appeals (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,employee_id uuid NOT NULL,actor_id uuid NOT NULL,reason text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TRIGGER behavior_records_immutable BEFORE UPDATE OR DELETE ON ago_behavior_records FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TRIGGER behavior_appeals_immutable BEFORE UPDATE OR DELETE ON ago_behavior_appeals FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
