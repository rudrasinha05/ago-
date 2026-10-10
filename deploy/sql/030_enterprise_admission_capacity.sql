-- AGO Section 21: persistent, race-safe organization/department/worker capacity.
-- No separate queue and no background self-execution. Existing TaskStore
-- remains the sole authorized action launcher.
CREATE TABLE ago_oos_capacity_policies (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 scope_kind text NOT NULL CHECK(scope_kind IN ('company','department','employee')),
 scope_id uuid,
 max_running integer NOT NULL CHECK(max_running BETWEEN 1 AND 1000),
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 rationale text NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 1500),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((scope_kind='company' AND scope_id IS NULL)
     OR (scope_kind<>'company' AND scope_id IS NOT NULL))
);
CREATE INDEX ago_oos_capacity_policy_history
 ON ago_oos_capacity_policies(tenant_id,scope_kind,scope_id,created_at DESC,id DESC);

CREATE FUNCTION ago_oos_capacity_review_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE review record; tablename text;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO review FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR review.status<>'approved'
 OR review.action IS DISTINCT FROM (
     'enterprise:capacity:'||NEW.scope_kind||':'||
      coalesce(NEW.scope_id::text,'company')||':'||NEW.max_running::text
 )
 OR review.requester_id<>NEW.actor_id OR review.reviewer_id IS NULL
 OR review.reviewer_id=review.requester_id
 THEN RAISE EXCEPTION 'Independent exact capacity review required'; END IF;
 IF NEW.scope_kind='department' AND NOT EXISTS (
   SELECT 1 FROM ago_departments WHERE tenant_id=NEW.tenant_id AND id=NEW.scope_id
 ) THEN RAISE EXCEPTION 'Department outside approved tenant'; END IF;
 IF NEW.scope_kind='employee' AND NOT EXISTS (
   SELECT 1 FROM ago_employees WHERE tenant_id=NEW.tenant_id AND id=NEW.scope_id
 ) THEN RAISE EXCEPTION 'Employee outside approved tenant'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_oos_capacity_review BEFORE INSERT ON ago_oos_capacity_policies
 FOR EACH ROW EXECUTE FUNCTION ago_oos_capacity_review_guard();
CREATE TRIGGER ago_oos_capacity_immutable BEFORE UPDATE OR DELETE ON ago_oos_capacity_policies
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_oos_task_capacity_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE department_id uuid; company_cap int; department_cap int; employee_cap int;
        company_running bigint; department_running bigint; employee_running bigint;
BEGIN
 IF NEW.status <> 'running' THEN RETURN NEW; END IF;
 IF TG_OP='UPDATE' AND OLD.status='running' THEN RETURN NEW; END IF;
 -- Serialize *all* admissions within the tenant. No two requests may both
 -- observe a free final slot; the committed task statuses are authoritative.
 PERFORM 1 FROM ago_tenants WHERE id=NEW.tenant_id FOR UPDATE;
 SELECT e.department_id INTO department_id FROM ago_employees e
 WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id;
 IF department_id IS NULL THEN RAISE EXCEPTION 'Scoped assigned worker not found'; END IF;
 SELECT p.max_running INTO company_cap FROM ago_oos_capacity_policies p
 WHERE p.tenant_id=NEW.tenant_id AND p.scope_kind='company' AND p.scope_id IS NULL
 ORDER BY p.created_at DESC,p.id DESC LIMIT 1;
 SELECT p.max_running INTO department_cap FROM ago_oos_capacity_policies p
 WHERE p.tenant_id=NEW.tenant_id AND p.scope_kind='department' AND p.scope_id=department_id
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
 WHERE t.tenant_id=NEW.tenant_id AND e.department_id=department_id AND t.status='running';
 SELECT count(*) INTO employee_running FROM ago_governed_tasks
 WHERE tenant_id=NEW.tenant_id AND assignee_id=NEW.assignee_id AND status='running';
 IF company_running>=company_cap OR department_running>=department_cap
    OR employee_running>=employee_cap THEN
    RAISE EXCEPTION 'OOS running capacity exceeded: human review/queue required';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_oos_capacity_on_task_start
 BEFORE INSERT OR UPDATE ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_oos_task_capacity_guard();
