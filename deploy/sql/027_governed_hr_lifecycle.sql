-- Section 21: reviewed AI workforce and department lifecycle without removing
-- historical M2 employee/department records or changing existing onboarding.
CREATE TABLE ago_personnel_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 employee_id uuid NOT NULL,
 change_kind text NOT NULL CHECK(change_kind IN ('hired','promoted','terminated')),
 role_level int NOT NULL CHECK(role_level BETWEEN 1 AND 5),
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE INDEX ago_personnel_history ON ago_personnel_events(tenant_id,employee_id,created_at DESC,id);

CREATE TABLE ago_department_lifecycle_events (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 department_id uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('created','closed')),
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 reason text NOT NULL CHECK(length(trim(reason)) BETWEEN 1 AND 2000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 UNIQUE(tenant_id,department_id,action),
 FOREIGN KEY(tenant_id,department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);

CREATE FUNCTION ago_personnel_approval_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record; last_event record; employee_kind text;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status<>'approved'
 OR a.action <> 'enterprise:hr:'||NEW.change_kind||':'||NEW.employee_id::text
 OR a.requester_id<>NEW.actor_id OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 THEN RAISE EXCEPTION 'Independent exact personnel approval required'; END IF;
 SELECT kind INTO employee_kind FROM ago_employees
 WHERE tenant_id=NEW.tenant_id AND id=NEW.employee_id;
 IF employee_kind IS DISTINCT FROM 'ai' THEN
    RAISE EXCEPTION 'Automated HR operations are restricted to registered AI workers'; END IF;
 SELECT change_kind,role_level INTO last_event FROM ago_personnel_events
 WHERE tenant_id=NEW.tenant_id AND employee_id=NEW.employee_id
 ORDER BY created_at DESC,id DESC LIMIT 1;
 IF FOUND AND last_event.change_kind='terminated' THEN
   RAISE EXCEPTION 'Terminated worker cannot be reactivated through history edits';
 END IF;
 IF NEW.change_kind='hired' AND FOUND THEN
   RAISE EXCEPTION 'AI hire must occur once';
 ELSIF NEW.change_kind='promoted' AND NEW.role_level<=coalesce(last_event.role_level,1) THEN
   RAISE EXCEPTION 'Promotion must strictly increase approved role level';
 ELSIF NEW.change_kind='terminated' AND
   EXISTS(SELECT 1 FROM ago_governed_tasks
      WHERE tenant_id=NEW.tenant_id AND assignee_id=NEW.employee_id AND status='running') THEN
   RAISE EXCEPTION 'Stop or finish in-flight tasks before termination';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_personnel_approval BEFORE INSERT ON ago_personnel_events
 FOR EACH ROW EXECUTE FUNCTION ago_personnel_approval_guard();
CREATE TRIGGER ago_personnel_immutable BEFORE UPDATE OR DELETE ON ago_personnel_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_department_change_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id,reviewer_id INTO a
 FROM ago_approval_requests WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status<>'approved'
 OR a.action <> 'enterprise:department:'||NEW.action||':'||NEW.department_id::text
 OR a.requester_id<>NEW.actor_id OR a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id
 THEN RAISE EXCEPTION 'Independent exact department approval required'; END IF;
 IF NEW.action='closed' AND EXISTS (
   SELECT 1 FROM ago_employees WHERE tenant_id=NEW.tenant_id
     AND department_id=NEW.department_id
 ) THEN RAISE EXCEPTION 'Nonempty department cannot be closed'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_department_review BEFORE INSERT ON ago_department_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION ago_department_change_guard();
CREATE TRIGGER ago_department_immutable BEFORE UPDATE OR DELETE ON ago_department_lifecycle_events
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- Fail closed when any older/manual API attempts new work for a terminated AI,
-- or to hire into a closed department.
CREATE FUNCTION ago_personnel_dispatch_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE eid uuid; tid uuid; dept uuid;
BEGIN
 IF NEW.status<>'running' THEN RETURN NEW; END IF;
 IF TG_TABLE_NAME='ago_governed_tasks' THEN
   IF TG_OP='UPDATE' AND OLD.status='running' THEN RETURN NEW; END IF;
   eid:=NEW.assignee_id;tid:=NEW.tenant_id;
 ELSE
   eid:=NEW.agent_id;tid:=NEW.tenant_id;
 END IF;
 SELECT department_id INTO dept FROM ago_employees
 WHERE tenant_id=tid AND id=eid;
 IF EXISTS (
    SELECT 1 FROM ago_personnel_events
    WHERE tenant_id=tid AND employee_id=eid AND change_kind='terminated'
 ) THEN RAISE EXCEPTION 'Terminated worker cannot execute work'; END IF;
 IF EXISTS (
   SELECT 1 FROM ago_department_lifecycle_events
   WHERE tenant_id=tid AND department_id=dept AND action='closed'
 ) THEN RAISE EXCEPTION 'Closed department cannot dispatch work'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_hr_task_dispatch BEFORE INSERT OR UPDATE ON ago_governed_tasks
 FOR EACH ROW EXECUTE FUNCTION ago_personnel_dispatch_guard();
CREATE TRIGGER ago_hr_agent_dispatch BEFORE INSERT ON ago_agent_runs
 FOR EACH ROW EXECUTE FUNCTION ago_personnel_dispatch_guard();

CREATE FUNCTION ago_closed_department_hire_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS (SELECT 1 FROM ago_department_lifecycle_events
   WHERE tenant_id=NEW.tenant_id AND department_id=NEW.department_id
   AND action='closed') THEN RAISE EXCEPTION 'Closed department cannot hire'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_closed_department_hire BEFORE INSERT OR UPDATE OF department_id ON ago_employees
 FOR EACH ROW EXECUTE FUNCTION ago_closed_department_hire_guard();
