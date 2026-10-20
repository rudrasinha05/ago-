-- AGO founder command center: explicit role accountability, board seats and upward reports.
-- No elevation of RBAC or autonomous execution from a board label.
ALTER TABLE ago_employees
  ADD COLUMN role_title text NOT NULL DEFAULT '' CHECK (length(role_title) <= 150),
  ADD COLUMN core_responsibilities text NOT NULL DEFAULT '' CHECK (length(core_responsibilities) <= 3000),
  ADD COLUMN extra_responsibilities text NOT NULL DEFAULT '' CHECK (length(extra_responsibilities) <= 3000);

CREATE TABLE ago_company_board_appointments (
  tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
  seat text NOT NULL CHECK (seat IN (
    'Strategy & Vision','Technology Oversight','Finance & Budget',
    'Risk & Compliance','Quality & Release'
  )),
  employee_id uuid NOT NULL,
  appointed_by uuid NOT NULL,
  appointed_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id,seat),
  UNIQUE (tenant_id,employee_id),
  FOREIGN KEY (tenant_id,employee_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,appointed_by) REFERENCES ago_users(tenant_id,id)
);

CREATE TABLE ago_company_reports (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
  author_id uuid NOT NULL,
  recipient_id uuid NOT NULL,
  kind text NOT NULL CHECK(kind IN ('doubt','blocker','module_complete','phase_complete')),
  body text NOT NULL CHECK (length(trim(body)) BETWEEN 1 AND 6000),
  task_id uuid,
  operation_key uuid NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id,author_id,operation_key),
  FOREIGN KEY (tenant_id,author_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,recipient_id) REFERENCES ago_employees(tenant_id,id),
  FOREIGN KEY (tenant_id,task_id) REFERENCES ago_governed_tasks(tenant_id,id),
  CHECK (author_id <> recipient_id)
);
CREATE INDEX ago_company_reports_inbox ON ago_company_reports(tenant_id,recipient_id,id DESC);
CREATE INDEX ago_company_reports_outbox ON ago_company_reports(tenant_id,author_id,id DESC);

-- Readable work events participate in the established durable company timeline.
ALTER TABLE ago_company_chat DROP CONSTRAINT ago_company_chat_kind_check;
ALTER TABLE ago_company_chat ADD CONSTRAINT ago_company_chat_kind_check
  CHECK(kind IN ('message','status','staffing','report','github','qa','docs'));

-- Disallow modifying historical reporting evidence, including deletion.
CREATE TRIGGER ago_company_reports_append_only BEFORE UPDATE OR DELETE ON ago_company_reports
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
