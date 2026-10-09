-- M2 durable approval decisions. All access must be tenant-scoped by the application.
CREATE TABLE IF NOT EXISTS ago_approval_requests (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 action text NOT NULL CHECK (length(trim(action)) > 0),
 requester_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','approved','rejected')),
 reviewer_id uuid,
 reason text,
 created_at timestamptz NOT NULL DEFAULT now(),
 decided_at timestamptz,
 CHECK ((status = 'pending' AND reviewer_id IS NULL AND decided_at IS NULL)
     OR (status <> 'pending' AND reviewer_id IS NOT NULL AND decided_at IS NOT NULL)),
 CHECK (reviewer_id IS NULL OR reviewer_id <> requester_id)
);
CREATE INDEX IF NOT EXISTS idx_ago_approvals_tenant_status
 ON ago_approval_requests(tenant_id, status, created_at DESC);
CREATE TABLE IF NOT EXISTS ago_approval_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 request_id uuid NOT NULL REFERENCES ago_approval_requests(id) ON DELETE RESTRICT,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 actor_id uuid NOT NULL,
 event text NOT NULL CHECK (event IN ('proposed','approved','rejected')),
 reason text,
 occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ago_approval_audit_request
 ON ago_approval_audit(request_id, occurred_at);
