CREATE TABLE ago_memory_projects (
 tenant_id uuid NOT NULL,
 goal_id uuid NOT NULL,
 user_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,goal_id,user_id),
 FOREIGN KEY(tenant_id,goal_id) REFERENCES ago_goals(tenant_id,id),
 FOREIGN KEY(tenant_id,user_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_scoped_memories (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 owner_id uuid NOT NULL,
 scope text NOT NULL CHECK(scope IN ('employee','department','project','company')),
 scope_id uuid NOT NULL,
 department_id uuid,
 goal_id uuid,
 employee_id uuid,
 kind text NOT NULL CHECK(kind IN ('episodic','working','summary')),
 content text,
 source_ref text NOT NULL CHECK(length(source_ref) BETWEEN 1 AND 1000),
 knowledge_id uuid,
 revision integer NOT NULL DEFAULT 1 CHECK(revision>0),
 state text NOT NULL DEFAULT 'active' CHECK(state IN ('active','forgotten','superseded')),
 created_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL,
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,owner_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,employee_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,department_id) REFERENCES ago_departments(tenant_id,id),
 FOREIGN KEY(tenant_id,goal_id) REFERENCES ago_goals(tenant_id,id),
 FOREIGN KEY(tenant_id,knowledge_id) REFERENCES ago_knowledge_nodes(tenant_id,id),
 CHECK((state='active' AND content IS NOT NULL AND length(trim(content)) BETWEEN 1 AND 12000)
       OR (state<>'active' AND content IS NULL)),
 CHECK((scope='employee' AND employee_id IS NOT NULL AND scope_id=employee_id AND employee_id=owner_id AND department_id IS NULL AND goal_id IS NULL)
    OR (scope='department' AND department_id IS NOT NULL AND scope_id=department_id AND employee_id IS NULL AND goal_id IS NULL)
    OR (scope='project' AND goal_id IS NOT NULL AND scope_id=goal_id AND employee_id IS NULL AND department_id IS NULL)
    OR (scope='company' AND scope_id=tenant_id AND employee_id IS NULL AND department_id IS NULL AND goal_id IS NULL)),
 CHECK(expires_at>created_at AND expires_at<=created_at+interval '365 days'),
 CHECK(kind<>'working' OR expires_at<=created_at+interval '24 hours')
);
CREATE INDEX idx_memory_scope ON ago_scoped_memories(tenant_id,scope,scope_id,expires_at) WHERE state='active';
CREATE TABLE ago_memory_vectors (
 tenant_id uuid NOT NULL,
 memory_id uuid NOT NULL,
 revision integer NOT NULL,
 model_id text NOT NULL,
 vector jsonb NOT NULL CHECK(jsonb_typeof(vector)='array' AND jsonb_array_length(vector)=384),
 PRIMARY KEY(tenant_id,memory_id),
 FOREIGN KEY(tenant_id,memory_id) REFERENCES ago_scoped_memories(tenant_id,id)
);
CREATE TABLE ago_memory_sources (
 tenant_id uuid NOT NULL,
 memory_id uuid NOT NULL,
 source_id uuid NOT NULL,
 source_revision integer NOT NULL,
 PRIMARY KEY(tenant_id,memory_id,source_id),
 FOREIGN KEY(tenant_id,memory_id) REFERENCES ago_scoped_memories(tenant_id,id),
 FOREIGN KEY(tenant_id,source_id) REFERENCES ago_scoped_memories(tenant_id,id),
 CHECK(memory_id<>source_id)
);
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT id,'founder','memory:manage' FROM ago_tenants ON CONFLICT DO NOTHING;
