CREATE TABLE ago_graph_versions (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),entity_id uuid NOT NULL,
 entity_kind text NOT NULL CHECK(entity_kind IN ('node','edge')),revision int NOT NULL CHECK(revision>0),
 payload jsonb NOT NULL CHECK(jsonb_typeof(payload)='object'),proposal_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(tenant_id,entity_id,revision),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id)
);
CREATE TRIGGER graph_versions_immutable BEFORE UPDATE OR DELETE ON ago_graph_versions
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
CREATE TABLE ago_graph_reindex (
 tenant_id uuid NOT NULL,memory_id uuid NOT NULL,graph_id uuid NOT NULL,revision int NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),completed_at timestamptz,
 PRIMARY KEY(tenant_id,memory_id,graph_id,revision),
 FOREIGN KEY(tenant_id,memory_id) REFERENCES ago_scoped_memories(tenant_id,id)
);
