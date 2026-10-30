-- Reader-owned, tenant-scoped notification acknowledgement; no work or QA approval.
CREATE TABLE ago_notification_read_cursors (
 tenant_id uuid NOT NULL,
 reader_id uuid NOT NULL,
 read_through_id bigint NOT NULL DEFAULT 0 CHECK (read_through_id >= 0),
 PRIMARY KEY (tenant_id, reader_id),
 FOREIGN KEY (tenant_id, reader_id) REFERENCES ago_users(tenant_id, id) ON DELETE CASCADE
);
CREATE INDEX ago_company_chat_notification_cursor
 ON ago_company_chat(tenant_id, id)
 WHERE kind IN ('status','report','staffing','github','qa','docs','project');
