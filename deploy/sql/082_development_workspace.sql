CREATE TABLE ago_workspace_revisions (
    tenant_id uuid NOT NULL,
    project_id uuid NOT NULL,
    task_id uuid NOT NULL,
    run_id uuid NOT NULL,
    revision integer NOT NULL CHECK (revision > 0),
    candidate jsonb NOT NULL,
    edited_by uuid NOT NULL,
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
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
    PRIMARY KEY (tenant_id, project_id, task_id, run_id, attempt_id)
);
