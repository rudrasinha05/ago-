-- Durable single-prompt project intake. This creates DRAFT scope only.
-- Approved plan activation, per-task approvals, GitHub, and release gates remain separate.
CREATE TABLE ago_founder_intakes (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 founder_id uuid NOT NULL,
 operation_key uuid NOT NULL,
 brief_digest text NOT NULL CHECK(length(brief_digest)=64),
 brief text NOT NULL CHECK(length(trim(brief)) BETWEEN 20 AND 12000),
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 220),
 goal_id uuid NOT NULL,
 plan_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,founder_id,operation_key),
 UNIQUE(tenant_id,goal_id),UNIQUE(tenant_id,plan_id),
 FOREIGN KEY(tenant_id,founder_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,goal_id) REFERENCES ago_goals(tenant_id,id),
 FOREIGN KEY(tenant_id,plan_id) REFERENCES ago_strategy_plans(tenant_id,id)
);
CREATE TABLE ago_founder_intake_stages (
 tenant_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 position integer NOT NULL CHECK(position BETWEEN 1 AND 5),
 stage text NOT NULL CHECK(stage IN ('discovery','architecture','implementation','quality','release')),
 deliverable text NOT NULL CHECK(length(trim(deliverable)) BETWEEN 10 AND 500),
 suggested_assignee_id uuid,
 plan_step_id uuid,
 PRIMARY KEY(tenant_id,intake_id,position),
 UNIQUE(tenant_id,intake_id,stage),
 FOREIGN KEY(tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,suggested_assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,plan_step_id) REFERENCES ago_plan_steps(tenant_id,id)
);
ALTER TABLE ago_company_chat DROP CONSTRAINT ago_company_chat_kind_check;
ALTER TABLE ago_company_chat ADD CONSTRAINT ago_company_chat_kind_check
 CHECK(kind IN ('message','status','staffing','report','github','qa','docs','project'));
CREATE TRIGGER ago_founder_intakes_append_only BEFORE UPDATE OR DELETE ON ago_founder_intakes
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
CREATE TRIGGER ago_founder_stages_append_only BEFORE UPDATE OR DELETE ON ago_founder_intake_stages
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
