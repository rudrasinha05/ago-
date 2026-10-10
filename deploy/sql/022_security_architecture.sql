ALTER TABLE ago_users ADD COLUMN session_version integer NOT NULL DEFAULT 0 CHECK(session_version>=0);
CREATE TABLE ago_mfa_factors (
 tenant_id uuid NOT NULL,
 user_id uuid NOT NULL,
 ciphertext text NOT NULL,
 last_step bigint NOT NULL DEFAULT -1,
 PRIMARY KEY(tenant_id,user_id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_mfa_enrollments (
 token_hash text PRIMARY KEY,
 tenant_id uuid NOT NULL,
 user_id uuid NOT NULL,
 ciphertext text NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_mfa_recovery_codes (
 tenant_id uuid NOT NULL,
 user_id uuid NOT NULL,
 code_hash text NOT NULL,
 PRIMARY KEY(tenant_id,user_id,code_hash),
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_identity_tickets (
 id uuid PRIMARY KEY,
 token_hash text NOT NULL UNIQUE,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 issuer_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('invitation','recovery')),
 email text NOT NULL,
 department_id uuid NOT NULL,
 user_id uuid,
 session_version integer,
 expires_at timestamptz NOT NULL,
 used_at timestamptz,
 FOREIGN KEY(tenant_id,issuer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,department_id) REFERENCES ago_departments(tenant_id,id),
 CHECK((kind='invitation' AND user_id IS NULL AND session_version IS NULL)
       OR (kind='recovery' AND user_id IS NOT NULL AND session_version IS NOT NULL AND user_id<>issuer_id))
);
CREATE TABLE ago_sso_bindings (
 tenant_id uuid NOT NULL,
 user_id uuid NOT NULL,
 issuer text NOT NULL,
 subject text NOT NULL,
 PRIMARY KEY(tenant_id,issuer,subject),
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_sso_states (
 state_hash text PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 browser_hash text NOT NULL,
 nonce text NOT NULL,
 verifier_ciphertext text NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
 consumed boolean NOT NULL DEFAULT false
);
CREATE TABLE ago_sso_handoffs (
 token_hash text PRIMARY KEY,
 browser_hash text NOT NULL,
 tenant_id uuid NOT NULL,
 user_id uuid NOT NULL,
 session_version integer NOT NULL,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '60 seconds',
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT id,'founder','security:manage' FROM ago_tenants ON CONFLICT DO NOTHING;
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT id,'member',p FROM ago_tenants CROSS JOIN unnest(ARRAY['organization:read','memory:read','memory:write','knowledge:read','task:read']) p
ON CONFLICT DO NOTHING;
