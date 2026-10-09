-- AGO identity foundation, PostgreSQL 15+.
CREATE TABLE IF NOT EXISTS ago_tenants (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS ago_users (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
    email text NOT NULL,
    password_hash text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, email),
    UNIQUE (tenant_id, id)
);
CREATE TABLE IF NOT EXISTS ago_user_roles (
    tenant_id uuid NOT NULL,
    user_id uuid NOT NULL,
    role text NOT NULL,
    PRIMARY KEY (tenant_id, user_id, role),
    FOREIGN KEY (tenant_id, user_id)
        REFERENCES ago_users(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_ago_users_tenant ON ago_users(tenant_id);
