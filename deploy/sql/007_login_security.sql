-- Brute-force protection for authenticated M2 API sessions (tenant/email scoped).
CREATE TABLE ago_login_attempts (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 email text NOT NULL,
 failures integer NOT NULL DEFAULT 0 CHECK (failures >= 0),
 blocked_until timestamptz,
 updated_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id, email)
);
CREATE INDEX idx_ago_login_attempts_blocked ON ago_login_attempts(blocked_until)
 WHERE blocked_until IS NOT NULL;
CREATE UNIQUE INDEX idx_ago_department_name_normalized
 ON ago_departments(tenant_id, lower(name));
