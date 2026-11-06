-- Preserve existing projects and immutable assignment history.
ALTER TABLE ago_founder_project_lead
 DROP CONSTRAINT ago_founder_project_lead_assignment_source_check;
ALTER TABLE ago_founder_project_lead ADD CONSTRAINT ago_founder_project_lead_assignment_source_check
 CHECK (assignment_source IN ('executive_manager','founder_escalation','founder_reassignment'));

CREATE TABLE ago_project_manager_changes (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 previous_manager_id uuid NOT NULL,
 manager_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 changed_at timestamptz NOT NULL,
 FOREIGN KEY (tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,previous_manager_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,manager_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 CHECK (previous_manager_id <> manager_id)
);
CREATE INDEX ago_project_manager_change_history
 ON ago_project_manager_changes(tenant_id,intake_id,id);
CREATE TRIGGER ago_project_manager_changes_immutable
 BEFORE UPDATE OR DELETE ON ago_project_manager_changes
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE FUNCTION ago_record_project_manager_change() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.accountable_manager_id IS DISTINCT FROM NEW.accountable_manager_id THEN
  INSERT INTO ago_project_manager_changes
   (tenant_id,intake_id,previous_manager_id,manager_id,actor_id,changed_at)
  VALUES (NEW.tenant_id,NEW.intake_id,OLD.accountable_manager_id,
          NEW.accountable_manager_id,NEW.assigned_by,NEW.assigned_at);
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_project_manager_change_audit
 AFTER UPDATE ON ago_founder_project_lead
 FOR EACH ROW EXECUTE FUNCTION ago_record_project_manager_change();
