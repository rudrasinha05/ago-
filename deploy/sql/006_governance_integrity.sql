-- M2 integrity hardening: tenant-safe references, no recycled approvals and append-only reviews.
ALTER TABLE ago_approval_requests
 ADD CONSTRAINT ago_approval_requests_tenant_id_key UNIQUE (tenant_id, id);
ALTER TABLE ago_governed_tasks
 ADD CONSTRAINT ago_task_approval_tenant_fk FOREIGN KEY (tenant_id, approval_id)
 REFERENCES ago_approval_requests(tenant_id, id);
ALTER TABLE ago_governed_tasks
 ADD CONSTRAINT ago_task_approval_unique UNIQUE (approval_id);
ALTER TABLE ago_approval_audit
 ADD CONSTRAINT ago_approval_audit_tenant_fk FOREIGN KEY (tenant_id, request_id)
 REFERENCES ago_approval_requests(tenant_id, id);

CREATE OR REPLACE FUNCTION ago_protect_append_only() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 RAISE EXCEPTION 'AGO audit/review history is append-only';
END;
$$;
CREATE TRIGGER ago_approval_audit_protect
 BEFORE UPDATE OR DELETE ON ago_approval_audit
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_task_reviews (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 task_id uuid NOT NULL,
 author_id uuid NOT NULL,
 reviewer_id uuid NOT NULL,
 verdict text NOT NULL CHECK (verdict IN ('pass','fail')),
 evidence text NOT NULL CHECK (length(trim(evidence)) > 0),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id, task_id),
 FOREIGN KEY (tenant_id, task_id) REFERENCES ago_governed_tasks(tenant_id, id),
 CHECK (reviewer_id <> author_id)
);
CREATE INDEX idx_ago_task_reviews_tenant_time
 ON ago_task_reviews(tenant_id, created_at DESC);
CREATE TRIGGER ago_task_reviews_protect
 BEFORE UPDATE OR DELETE ON ago_task_reviews
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
