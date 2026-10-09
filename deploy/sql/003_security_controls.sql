-- Persistent security controls for PostgreSQL 15+.
CREATE TABLE IF NOT EXISTS ago_role_permissions (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 role text NOT NULL,
 permission text NOT NULL,
 PRIMARY KEY (tenant_id, role, permission)
);
CREATE TABLE IF NOT EXISTS ago_revoked_sessions (
 token_hash text PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL,
 revoked_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ago_revoked_sessions_expiry ON ago_revoked_sessions(expires_at);
CREATE TABLE IF NOT EXISTS ago_security_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid REFERENCES ago_tenants(id),
 actor_id uuid,
 action text NOT NULL,
 outcome text NOT NULL,
 metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
 occurred_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ago_security_audit_tenant_time
 ON ago_security_audit(tenant_id, occurred_at DESC);
