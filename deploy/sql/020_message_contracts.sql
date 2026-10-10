ALTER TABLE event_outbox ADD COLUMN tenant_id uuid REFERENCES ago_tenants(id);
ALTER TABLE event_outbox ADD COLUMN actor_id uuid;
ALTER TABLE event_outbox ADD COLUMN message_kind text CHECK(message_kind IN ('command','event','query','notification','approval'));
ALTER TABLE event_outbox ADD COLUMN operation_key text;
ALTER TABLE event_outbox ADD COLUMN ordering_key text;
ALTER TABLE event_outbox ADD COLUMN sequence bigint GENERATED ALWAYS AS IDENTITY;
ALTER TABLE event_outbox ADD COLUMN body_sha256 text;
ALTER TABLE event_outbox ADD COLUMN lease_token uuid;
ALTER TABLE event_outbox ADD COLUMN cycle_attempts integer NOT NULL DEFAULT 0 CHECK(cycle_attempts>=0);
ALTER TABLE event_outbox ADD COLUMN replay_count integer NOT NULL DEFAULT 0 CHECK(replay_count>=0);
ALTER TABLE event_outbox ADD FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id);
ALTER TABLE event_outbox ADD CHECK(message_kind IS NULL OR
  (tenant_id IS NOT NULL AND actor_id IS NOT NULL
   AND operation_key IS NOT NULL AND body_sha256 IS NOT NULL AND length(operation_key) BETWEEN 1 AND 150 AND ordering_key IS NOT NULL
   AND length(ordering_key) BETWEEN 1 AND 150 AND body_sha256 ~ '^[a-f0-9]{64}$'));
CREATE UNIQUE INDEX idx_message_idempotency ON event_outbox(tenant_id,operation_key) WHERE message_kind IS NOT NULL;
CREATE INDEX idx_message_order ON event_outbox(tenant_id,ordering_key,sequence) WHERE message_kind IS NOT NULL;
CREATE TABLE ago_message_receipts (
  tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
  event_id uuid NOT NULL REFERENCES event_outbox(id),
  consumer text NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  result jsonb NOT NULL,
  PRIMARY KEY(tenant_id,event_id,consumer)
);
CREATE TRIGGER ago_message_receipts_immutable BEFORE UPDATE OR DELETE ON ago_message_receipts
FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
CREATE FUNCTION ago_guard_message_body() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF OLD.message_kind IS NOT NULL AND ROW(NEW.id,NEW.name,NEW.payload,NEW.tenant_id,NEW.actor_id,
     NEW.message_kind,NEW.operation_key,NEW.ordering_key,NEW.sequence,NEW.body_sha256,
     NEW.occurred_at,NEW.correlation_id) IS DISTINCT FROM
    ROW(OLD.id,OLD.name,OLD.payload,OLD.tenant_id,OLD.actor_id,OLD.message_kind,OLD.operation_key,
     OLD.ordering_key,OLD.sequence,OLD.body_sha256,OLD.occurred_at,OLD.correlation_id) THEN
   RAISE EXCEPTION 'Message identity and body are immutable';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_message_body BEFORE UPDATE ON event_outbox FOR EACH ROW EXECUTE FUNCTION ago_guard_message_body();
INSERT INTO ago_role_permissions(tenant_id,role,permission)
SELECT id,'founder',p FROM ago_tenants CROSS JOIN unnest(ARRAY['messages:read','messages:write','messages:replay']) p
ON CONFLICT DO NOTHING;
