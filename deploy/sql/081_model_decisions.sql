-- MGR-002: the Workforce Manager's model choice for each piece of AI work,
-- with its reason. A record of a decision only: it grants no authority.
CREATE TABLE ago_model_decisions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 task_id uuid,
 work text NOT NULL CHECK(work IN ('code','qa','plan','board','chat','learn')),
 role text CHECK(role IS NULL OR length(role) <= 20),
 model_label text NOT NULL CHECK(length(model_label) BETWEEN 3 AND 200),
 reason text NOT NULL CHECK(length(reason) BETWEEN 3 AND 600),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id)
);
CREATE INDEX ago_model_decisions_recent ON ago_model_decisions(tenant_id,created_at DESC);

CREATE FUNCTION ago_guard_model_decision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'Model decisions are append-only';
END $$;
CREATE TRIGGER ago_model_decisions_guard BEFORE UPDATE OR DELETE ON ago_model_decisions
 FOR EACH ROW EXECUTE FUNCTION ago_guard_model_decision();
