CREATE TABLE ago_workspace_revisions (
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    run_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    candidate jsonb NOT NULL,
    edited_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    FOREIGN KEY (tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
    FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
    PRIMARY KEY (tenant_id, project_id, task_id, run_id, revision)
);

CREATE TABLE ago_workspace_test_runs (
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    run_id uuid NOT NULL,
    attempt_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision >= 0),
    candidate_sha256 text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    finished_at timestamptz,
    receipt jsonb,
    FOREIGN KEY (tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
    FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
    CHECK ((finished_at IS NULL) = (receipt IS NULL)),
    PRIMARY KEY (tenant_id, project_id, task_id, run_id, attempt_id)
);

CREATE FUNCTION ago_guard_workspace_revision() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'Workspace revisions are immutable';
END;
$$;
CREATE TRIGGER ago_workspace_revision_guard BEFORE UPDATE OR DELETE ON ago_workspace_revisions
FOR EACH ROW EXECUTE FUNCTION ago_guard_workspace_revision();

CREATE FUNCTION ago_guard_workspace_receipt() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP = 'DELETE' OR OLD.finished_at IS NOT NULL THEN
        RAISE EXCEPTION 'Workspace execution evidence is immutable';
    END IF;
    IF (to_jsonb(NEW) - ARRAY['receipt','finished_at']) IS DISTINCT FROM
       (to_jsonb(OLD) - ARRAY['receipt','finished_at'])
       OR NEW.finished_at IS NULL OR NEW.receipt IS NULL
       OR NEW.receipt->>'candidate_sha256' IS DISTINCT FROM OLD.candidate_sha256 THEN
        RAISE EXCEPTION 'Workspace receipt must finalize its original candidate';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER ago_workspace_receipt_guard BEFORE UPDATE OR DELETE ON ago_workspace_test_runs
FOR EACH ROW EXECUTE FUNCTION ago_guard_workspace_receipt();

CREATE TABLE ago_workspace_terminal (
    tenant_id uuid NOT NULL, project_id uuid NOT NULL, task_id uuid NOT NULL, run_id uuid NOT NULL,
    attempt_id uuid NOT NULL, revision integer NOT NULL, candidate_sha256 text NOT NULL,
    entry text NOT NULL, output text NOT NULL DEFAULT '', exit_code integer,
    started_at timestamptz NOT NULL DEFAULT clock_timestamp(), finished_at timestamptz,
    stop_requested boolean NOT NULL DEFAULT false, status text NOT NULL DEFAULT 'running',
    FOREIGN KEY (tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
    FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
    PRIMARY KEY (tenant_id,project_id,task_id,run_id,attempt_id)
);
