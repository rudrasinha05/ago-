-- Independent AI QA receipts (issue #8 M4). In a company whose only human is
-- the Founder, a finished stage task is quality-checked by an AI QA employee
-- who did not build it. Every attempt keeps the exact model receipt: what was
-- asked (hash), what the model answered (bounded text + hash), which model,
-- the credit usage and the parsed verdict. Only a PASS/FAIL attempt also
-- writes the ordinary ago_task_reviews row (through QualityStore); an
-- 'unverified' answer records nothing as a review.
CREATE TABLE ago_ai_qa_reviews (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 qa_employee_id uuid NOT NULL,
 author_id uuid NOT NULL,
 requested_by uuid NOT NULL,
 model text NOT NULL CHECK (length(trim(model)) BETWEEN 1 AND 200),
 provider_mode text NOT NULL CHECK (provider_mode IN ('ollama_local')),
 prompt_sha256 text NOT NULL CHECK (prompt_sha256 ~ '^[0-9a-f]{64}$'),
 response_sha256 text NOT NULL CHECK (response_sha256 ~ '^[0-9a-f]{64}$'),
 response_text text NOT NULL CHECK (length(response_text) BETWEEN 1 AND 4000),
 verdict text NOT NULL CHECK (verdict IN ('pass','fail','unverified')),
 credit_usage_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,qa_employee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,requested_by) REFERENCES ago_users(tenant_id,id),
 CHECK (qa_employee_id <> author_id)
);
-- At most one decided (pass/fail) AI QA verdict per task, like ago_task_reviews.
CREATE UNIQUE INDEX ago_ai_qa_one_verdict
 ON ago_ai_qa_reviews(tenant_id,task_id) WHERE verdict IN ('pass','fail');
CREATE INDEX ago_ai_qa_history ON ago_ai_qa_reviews(tenant_id,task_id,created_at DESC);
CREATE TRIGGER ago_ai_qa_reviews_immutable
 BEFORE UPDATE OR DELETE ON ago_ai_qa_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
