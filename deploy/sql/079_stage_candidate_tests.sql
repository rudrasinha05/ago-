-- QA-002 / QA-003: AGO runs the implementation stage's generated tests itself.
-- One receipt per stage task: inserted as 'started' BEFORE the container runs
-- (a crash leaves visible evidence and blocks a silent replay), then finalized
-- exactly once. The receipt never grants QA, commit or release by itself.
CREATE TABLE ago_stage_candidate_tests (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 project_id uuid NOT NULL,
 task_id uuid NOT NULL,
 run_id uuid NOT NULL,
 candidate_sha256 text NOT NULL CHECK(candidate_sha256 ~ '^[0-9a-f]{64}$'),
 status text NOT NULL CHECK(status IN ('started','passed','failed','timeout','interrupted')),
 unittest_cases integer NOT NULL DEFAULT 0 CHECK(unittest_cases BETWEEN 0 AND 10000),
 failure_category text NOT NULL DEFAULT 'none' CHECK(length(failure_category) BETWEEN 1 AND 60),
 failure_summary text NOT NULL DEFAULT '' CHECK(length(failure_summary) <= 1000),
 docker_exit_code integer,
 output_sha256 text CHECK(output_sha256 IS NULL OR output_sha256 ~ '^[0-9a-f]{64}$'),
 started_by uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 finished_at timestamptz,
 UNIQUE(tenant_id,task_id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 CHECK((status='started')=(finished_at IS NULL)),
 CHECK(status<>'passed' OR unittest_cases>=1)
);

CREATE FUNCTION ago_guard_stage_candidate_test() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='INSERT' THEN
  IF NEW.status<>'started' THEN
   RAISE EXCEPTION 'A candidate test receipt starts as started';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM ago_agent_runs r
                 WHERE r.tenant_id=NEW.tenant_id AND r.id=NEW.run_id
                   AND r.task_id=NEW.task_id AND r.status='completed') THEN
   RAISE EXCEPTION 'Only a completed run of this task can be tested';
  END IF;
  RETURN NEW;
 END IF;
 IF TG_OP='UPDATE' AND OLD.status='started' AND NEW.status<>'started'
    AND (to_jsonb(OLD)-'status'-'unittest_cases'-'failure_category'-'failure_summary'
         -'docker_exit_code'-'output_sha256'-'finished_at')
      =(to_jsonb(NEW)-'status'-'unittest_cases'-'failure_category'-'failure_summary'
         -'docker_exit_code'-'output_sha256'-'finished_at') THEN
  RETURN NEW;
 END IF;
 RAISE EXCEPTION 'Candidate test receipts are immutable once finished';
END $$;
CREATE TRIGGER ago_stage_candidate_tests_guard BEFORE INSERT OR UPDATE OR DELETE
 ON ago_stage_candidate_tests FOR EACH ROW EXECUTE FUNCTION ago_guard_stage_candidate_test();
