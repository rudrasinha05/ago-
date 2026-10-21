-- AGO local-only company documents. Per-document READ grants, deny by default.
-- Never copy customer/founder data to public GitHub, tools or global chat.
CREATE TABLE ago_company_documents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 project_id uuid NOT NULL,
 created_by uuid NOT NULL,
 title text NOT NULL CHECK(length(btrim(title)) BETWEEN 1 AND 180),
 classification text NOT NULL CHECK(classification IN ('founder_only','project_restricted')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,created_by) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_company_documents_by_project
 ON ago_company_documents(tenant_id,project_id,created_at DESC);
CREATE TRIGGER ago_company_documents_immutable
 BEFORE UPDATE OR DELETE ON ago_company_documents
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_company_document_revisions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 document_id uuid NOT NULL,
 revision integer NOT NULL CHECK(revision>0),
 author_id uuid NOT NULL,
 body text NOT NULL CHECK(length(body) BETWEEN 1 AND 20000),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,document_id,revision),
 FOREIGN KEY(tenant_id,document_id) REFERENCES ago_company_documents(tenant_id,id),
 FOREIGN KEY(tenant_id,author_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TRIGGER ago_company_document_revisions_immutable
 BEFORE UPDATE OR DELETE ON ago_company_document_revisions
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- Access grant/revoke history is never overwritten. Last event wins.
CREATE TABLE ago_company_document_acl_events (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL,
 document_id uuid NOT NULL,
 grantee_id uuid NOT NULL,
 event text NOT NULL CHECK(event IN ('grant','revoke')),
 actor_id uuid NOT NULL,
 rationale text NOT NULL CHECK(length(btrim(rationale)) BETWEEN 8 AND 500),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(tenant_id,document_id) REFERENCES ago_company_documents(tenant_id,id),
 FOREIGN KEY(tenant_id,grantee_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_document_acl_resolve ON ago_company_document_acl_events
 (tenant_id,document_id,grantee_id,id DESC);
CREATE TRIGGER ago_document_acl_immutable
 BEFORE UPDATE OR DELETE ON ago_company_document_acl_events
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- Non-content access trail: no document title, text, authentication token or
-- body is copied into audit. Denials are included.
CREATE TABLE ago_company_document_access_audit (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 document_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('list','read','revise','grant','revoke','denied')),
 occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(tenant_id,document_id) REFERENCES ago_company_documents(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_document_audit_recent
 ON ago_company_document_access_audit(tenant_id,document_id,id DESC);
CREATE TRIGGER ago_document_access_audit_immutable
 BEFORE UPDATE OR DELETE ON ago_company_document_access_audit
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
