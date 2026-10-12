CREATE TABLE ago_analytics_settings (
 tenant_id uuid NOT NULL,id uuid NOT NULL,revision int NOT NULL,kind text NOT NULL CHECK(kind IN ('metric','schedule')),
 payload jsonb NOT NULL,proposal_id uuid NOT NULL,PRIMARY KEY(tenant_id,id,revision),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id)
);
CREATE TABLE ago_analytics_snapshots (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,actor_id uuid NOT NULL,operation_key text NOT NULL,
 projection jsonb NOT NULL,digest text NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,operation_key),FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_analytics_reports (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),schedule_id uuid NOT NULL,period text NOT NULL,
 report jsonb NOT NULL,alerts jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,schedule_id,period)
);
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['ago_analytics_settings','ago_analytics_snapshots','ago_analytics_reports'] LOOP
 EXECUTE format('CREATE TRIGGER analytics_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only()',t);
END LOOP;END $$;
