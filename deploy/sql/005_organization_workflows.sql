-- M2 tenant-scoped organizational and workflow persistence.
CREATE TABLE IF NOT EXISTS ago_departments (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 name text NOT NULL CHECK (length(trim(name)) > 0),
 UNIQUE(tenant_id, id),
 UNIQUE(tenant_id, name)
);
CREATE TABLE IF NOT EXISTS ago_employees (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 department_id uuid NOT NULL,
 name text NOT NULL CHECK (length(trim(name)) > 0),
 kind text NOT NULL CHECK (kind IN ('human','ai')),
 manager_id uuid,
 UNIQUE(tenant_id, id),
 FOREIGN KEY (tenant_id, department_id) REFERENCES ago_departments(tenant_id, id),
 FOREIGN KEY (tenant_id, manager_id) REFERENCES ago_employees(tenant_id, id),
 CHECK (id <> manager_id)
);
CREATE TABLE IF NOT EXISTS ago_governed_tasks (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 action text NOT NULL CHECK (length(trim(action)) > 0),
 assignee_id uuid NOT NULL,
 status text NOT NULL CHECK (status IN ('proposed','waiting_approval','ready','running','completed','failed')),
 approval_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id, id),
 FOREIGN KEY (tenant_id, assignee_id) REFERENCES ago_employees(tenant_id, id),
 FOREIGN KEY (approval_id) REFERENCES ago_approval_requests(id),
 CHECK ((status='proposed' AND approval_id IS NULL) OR (status<>'proposed' AND approval_id IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_ago_tasks_tenant_status ON ago_governed_tasks(tenant_id, status);
CREATE TABLE IF NOT EXISTS ago_memory_records (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 owner_id uuid NOT NULL,
 content text NOT NULL CHECK (length(trim(content)) > 0),
 visibility text NOT NULL CHECK (visibility IN ('private','tenant')),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ago_memory_tenant_owner ON ago_memory_records(tenant_id, owner_id);
