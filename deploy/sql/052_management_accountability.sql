-- AGO: accountable delivery ownership belongs to management, never merely the worker.
-- Every governed task receives a tenant-valid responsible employee on INSERT;
-- unmanaged standalone tenants receive a visible management-escalation flag.
-- Existing company/tenant tasks are safely backfilled; no task is executed here.
ALTER TABLE ago_governed_tasks ADD COLUMN accountable_manager_id uuid;
ALTER TABLE ago_governed_tasks ADD COLUMN management_escalation_required boolean NOT NULL DEFAULT false;
CREATE FUNCTION ago_assign_task_manager() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE supervisor uuid;
BEGIN
  SELECT e.manager_id INTO supervisor FROM ago_employees e
  WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id;
  IF supervisor IS NULL THEN
    SELECT e.id INTO supervisor FROM ago_employees e
    JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id AND r.role='founder'
    JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
    WHERE e.tenant_id=NEW.tenant_id AND e.kind='human'
    ORDER BY e.id LIMIT 1;
  END IF;
  -- Historical standalone/sandbox tenants can have no active founder at all.
  -- Do not invent a manager: keep an accountable executor and flag leadership gap.
  NEW.management_escalation_required := supervisor IS NULL;
  IF supervisor IS NULL THEN
    supervisor := NEW.assignee_id;
  END IF;
  NEW.accountable_manager_id := supervisor;
  RETURN NEW;
END $$;
CREATE TRIGGER ago_task_accountable_manager
 BEFORE INSERT OR UPDATE OF assignee_id ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_assign_task_manager();

UPDATE ago_governed_tasks t SET accountable_manager_id=
  COALESCE((SELECT e.manager_id FROM ago_employees e
            WHERE e.tenant_id=t.tenant_id AND e.id=t.assignee_id),
           (SELECT e.id FROM ago_employees e
            JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id AND r.role='founder'
            JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
            WHERE e.tenant_id=t.tenant_id AND e.kind='human'
            ORDER BY e.id LIMIT 1),t.assignee_id)
 WHERE t.accountable_manager_id IS NULL;
UPDATE ago_governed_tasks t SET management_escalation_required=true
WHERE NOT EXISTS (
 SELECT 1 FROM ago_employees e
 WHERE e.tenant_id=t.tenant_id AND e.id=t.assignee_id AND e.manager_id IS NOT NULL
) AND NOT EXISTS (
 SELECT 1 FROM ago_employees e
 JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id AND r.role='founder'
 JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
 WHERE e.tenant_id=t.tenant_id AND e.kind='human'
);

-- All governed actions have an accountable identity; unmanaged tasks are explicitly flagged.
ALTER TABLE ago_governed_tasks ALTER COLUMN accountable_manager_id SET NOT NULL;
ALTER TABLE ago_governed_tasks ADD CONSTRAINT ago_task_manager_fk
 FOREIGN KEY(tenant_id,accountable_manager_id) REFERENCES ago_employees(tenant_id,id);
CREATE INDEX ago_tasks_manager_workload
 ON ago_governed_tasks(tenant_id,accountable_manager_id,status);

-- Project commercial direction is a goal, not a fabricated contract/revenue record.
CREATE TABLE ago_founder_project_lead (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 intake_id uuid NOT NULL,
 accountable_manager_id uuid NOT NULL,
 assigned_by uuid NOT NULL,
 assignment_source text NOT NULL
  CHECK(assignment_source IN('executive_manager','founder_escalation')),
 commercial_objective text NOT NULL DEFAULT 'Find paying customers with a validated offer and earn verifiable revenue',
 commercial_stage text NOT NULL DEFAULT 'offer_needed'
  CHECK(commercial_stage IN('offer_needed','validation_needed','customer_evidence_required')),
 verified_revenue_inr numeric(15,2), -- NULL = no verified revenue evidence; not a zero claim.
 assigned_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(tenant_id,intake_id),
 FOREIGN KEY(tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,accountable_manager_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,assigned_by) REFERENCES ago_users(tenant_id,id),
 CHECK(verified_revenue_inr IS NULL OR verified_revenue_inr>=0)
);
CREATE INDEX ago_project_lead_manager
 ON ago_founder_project_lead(tenant_id,accountable_manager_id);

-- Existing projects become founder escalations instead of falsely receiving a CEO.
INSERT INTO ago_founder_project_lead
 (tenant_id,intake_id,accountable_manager_id,assigned_by,assignment_source)
SELECT i.tenant_id,i.id,i.founder_id,i.founder_id,'founder_escalation'
FROM ago_founder_intakes i;
