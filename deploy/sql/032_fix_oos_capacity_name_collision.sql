-- Additive correction after 030/031; preserve historical migrations.
-- PostgreSQL PL/pgSQL name resolution must not confuse a variable with
-- ago_employees.department_id during BEFORE UPDATE task admission.
CREATE OR REPLACE FUNCTION ago_oos_task_capacity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE worker_department_uuid uuid; company_cap int; department_cap int; employee_cap int;
        company_running bigint; department_running bigint; employee_running bigint;
BEGIN
 IF NEW.status <> 'running' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND OLD.status='running' THEN RETURN NEW; END IF;
 -- Serialize *all* admissions within the tenant. No two requests may both
 -- observe a free final slot; the committed task statuses are authoritative.
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 SELECT e.department_id INTO worker_department_uuid FROM ago_employees e
 WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id;
 IF worker_department_uuid IS NULL THEN RAISE EXCEPTION 'Scoped assigned worker not found'; END IF;
 SELECT p.max_running INTO company_cap FROM ago_oos_capacity_policies p
 WHERE p.tenant_id=NEW.tenant_id AND p.scope_kind='company' AND p.scope_id IS NULL
 ORDER BY p.created_at DESC,p.id DESC LIMIT 1;
 SELECT p.max_running INTO department_cap FROM ago_oos_capacity_policies p
 WHERE p.tenant_id=NEW.tenant_id AND p.scope_kind='department' AND p.scope_id=worker_department_uuid
 ORDER BY p.created_at DESC,p.id DESC LIMIT 1;
 SELECT p.max_running INTO employee_cap FROM ago_oos_capacity_policies p
 WHERE p.tenant_id=NEW.tenant_id AND p.scope_kind='employee' AND p.scope_id=NEW.assignee_id
 ORDER BY p.created_at DESC,p.id DESC LIMIT 1;
 company_cap:=coalesce(company_cap,12);
 department_cap:=coalesce(department_cap,4);
 employee_cap:=coalesce(employee_cap,1);
 SELECT count(*) INTO company_running FROM ago_governed_tasks
 WHERE tenant_id=NEW.tenant_id AND status='running';
 SELECT count(*) INTO department_running FROM ago_governed_tasks t
 JOIN ago_employees e ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id
 WHERE t.tenant_id=NEW.tenant_id AND e.department_id=worker_department_uuid AND t.status='running';
 SELECT count(*) INTO employee_running FROM ago_governed_tasks
 WHERE tenant_id=NEW.tenant_id AND assignee_id=NEW.assignee_id AND status='running';
 IF company_running>=company_cap OR department_running>=department_cap
    OR employee_running>=employee_cap THEN
    RAISE EXCEPTION 'OOS running capacity exceeded: human review/queue required';
 END IF;
 RETURN NEW;
END;
$$;
