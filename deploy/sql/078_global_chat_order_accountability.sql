-- 078: Founder-visible Global Chat order accountability. An intake receipt is NOT AI acknowledgement.
-- The worker's actual response/execution must be verified separately.
ALTER TABLE ago_company_chat ADD CONSTRAINT ago_company_chat_tenant_message_unique UNIQUE (tenant_id,id);
CREATE TABLE ago_chat_orders (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 message_id bigint NOT NULL,
 founder_order boolean NOT NULL,
 accountable_ceo_id uuid,
 intent text NOT NULL CHECK (intent IN ('message','order')),
 mention_ids jsonb NOT NULL DEFAULT '[]'::jsonb CHECK (jsonb_typeof(mention_ids)='array'),
 receipt_message_id bigint,
 state text NOT NULL CHECK (state IN ('awaiting_ack','blocked_no_ceo')),
 created_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY (tenant_id,message_id),
 FOREIGN KEY (tenant_id,message_id) REFERENCES ago_company_chat(tenant_id,id),
 FOREIGN KEY (tenant_id,receipt_message_id) REFERENCES ago_company_chat(tenant_id,id),
 FOREIGN KEY (tenant_id,accountable_ceo_id) REFERENCES ago_employees(tenant_id,id)
);
CREATE INDEX ago_chat_orders_ceo ON ago_chat_orders(tenant_id,accountable_ceo_id,message_id DESC);

CREATE TABLE ago_chat_work_items (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 message_id bigint NOT NULL,
 assignee_id uuid NOT NULL,
 accountable_ceo_id uuid,
 status text NOT NULL DEFAULT 'awaiting_ack'
  CHECK (status IN ('awaiting_ack','acknowledged','task_linked','working','blocked','completed')),
 linked_task_id uuid,
 ack_message_id bigint,
 response_claim_token uuid,
 response_claimed_at timestamptz,
 response_attempts integer NOT NULL DEFAULT 0 CHECK (response_attempts BETWEEN 0 AND 3),
 created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,message_id,assignee_id),
 FOREIGN KEY (tenant_id,message_id) REFERENCES ago_chat_orders(tenant_id,message_id),
 FOREIGN KEY (tenant_id,ack_message_id) REFERENCES ago_company_chat(tenant_id,id),
 FOREIGN KEY (tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,accountable_ceo_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY (tenant_id,linked_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 CHECK ((status IN ('task_linked','working','completed')) = (linked_task_id IS NOT NULL)
       OR status='blocked')
);
CREATE INDEX ago_chat_work_items_assignee
 ON ago_chat_work_items(tenant_id,assignee_id,status,created_at DESC);
CREATE INDEX ago_chat_work_items_message ON ago_chat_work_items(tenant_id,message_id);
