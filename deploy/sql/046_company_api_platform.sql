CREATE TABLE ago_integration_settings (
 tenant_id uuid NOT NULL,id uuid NOT NULL,revision int NOT NULL,kind text NOT NULL CHECK(kind IN ('client','webhook','plugin','version')),
 payload jsonb NOT NULL,proposal_id uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(tenant_id,id,revision),
 FOREIGN KEY(tenant_id,proposal_id) REFERENCES ago_enterprise_proposals(tenant_id,id)
);
CREATE TABLE ago_integration_credentials (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),client_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('api_key','client_secret','access_token')),secret_hash text NOT NULL UNIQUE,
 scopes text[] NOT NULL,expires_at timestamptz NOT NULL,revoked_at timestamptz,created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE ago_oauth_codes (
 code_hash text PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),client_id uuid NOT NULL,
 subject_id uuid NOT NULL,redirect_uri text NOT NULL,challenge text NOT NULL,scopes text[] NOT NULL,
 expires_at timestamptz NOT NULL,used_at timestamptz,
 FOREIGN KEY(tenant_id,subject_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TABLE ago_api_quotas (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id),axis text NOT NULL,key text NOT NULL,bucket bigint NOT NULL,hits int NOT NULL,
 PRIMARY KEY(tenant_id,axis,key,bucket)
);
CREATE TABLE ago_integration_events (
 sequence bigint GENERATED ALWAYS AS IDENTITY UNIQUE,id uuid PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),
 event_type text NOT NULL,source_key text NOT NULL,payload jsonb NOT NULL,subject_id uuid,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),UNIQUE(tenant_id,source_key),UNIQUE(tenant_id,id)
);
CREATE TABLE ago_webhook_keys (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL REFERENCES ago_tenants(id),subscription_id uuid NOT NULL,
 ciphertext text NOT NULL,active bool NOT NULL DEFAULT true,created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE UNIQUE INDEX webhook_active_key ON ago_webhook_keys(tenant_id,subscription_id) WHERE active;
CREATE TABLE ago_webhook_deliveries (
 id uuid PRIMARY KEY,tenant_id uuid NOT NULL,subscription_id uuid NOT NULL,event_id uuid NOT NULL,
 status text NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','retry','delivered','dead','blocked')),
 attempts int NOT NULL DEFAULT 0,last_status int,next_attempt_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),UNIQUE(tenant_id,subscription_id,event_id),
 FOREIGN KEY(tenant_id,event_id) REFERENCES ago_integration_events(tenant_id,id)
);
CREATE INDEX webhook_due ON ago_webhook_deliveries(tenant_id,next_attempt_at) WHERE status IN ('pending','retry');
CREATE TABLE ago_webhook_attempts (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,tenant_id uuid NOT NULL,delivery_id uuid NOT NULL,
 attempt int NOT NULL,status int,created_at timestamptz NOT NULL DEFAULT clock_timestamp()
);
CREATE TABLE ago_integration_commands (
 tenant_id uuid NOT NULL,client_id uuid NOT NULL,operation_key text NOT NULL,request_digest text NOT NULL,
 result jsonb NOT NULL,created_at timestamptz NOT NULL DEFAULT clock_timestamp(),PRIMARY KEY(tenant_id,client_id,operation_key)
);
DO $$ DECLARE t text; BEGIN FOREACH t IN ARRAY ARRAY['ago_integration_settings','ago_integration_events','ago_webhook_attempts','ago_integration_commands'] LOOP
 EXECUTE format('CREATE TRIGGER integration_immutable BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only()',t);
END LOOP;END $$;
-- Promote only explicit integration DTOs atomically with authoritative state changes.
CREATE FUNCTION ago_promote_integration_event() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE typename text; item jsonb; subject uuid; source text;
BEGIN
 IF TG_TABLE_NAME='ago_governed_tasks' THEN
  IF TG_OP='UPDATE' AND NEW.status=OLD.status THEN RETURN NEW; END IF;
  typename:='task.changed.v1';subject:=NEW.assignee_id;
  source:='task:'||NEW.id::text||':'||NEW.status||':'||NEW.updated_at::text;
  item:=jsonb_build_object('schema',typename,'task_id',NEW.id,'status',NEW.status,'observed_at',NEW.updated_at);
 ELSIF TG_TABLE_NAME='ago_approval_requests' THEN
  IF TG_OP='UPDATE' AND NEW.status=OLD.status THEN RETURN NEW; END IF;
  typename:='approval.changed.v1';subject:=NEW.requester_id;
  source:='approval:'||NEW.id::text||':'||NEW.status;
  item:=jsonb_build_object('schema',typename,'approval_id',NEW.id,'status',NEW.status);
 ELSIF TG_TABLE_NAME='ago_analytics_reports' THEN
  typename:='report.created.v1';source:='report:'||NEW.id::text;
  item:=jsonb_build_object('schema',typename,'report_id',NEW.id,'period',NEW.period);
 ELSE
  typename:='integration.changed.v1';source:='integration:'||NEW.id::text||':'||NEW.revision::text;
  item:=jsonb_build_object('schema',typename,'integration_id',NEW.id,'kind',NEW.kind,'revision',NEW.revision);
 END IF;
 INSERT INTO ago_integration_events(id,tenant_id,event_type,source_key,payload,subject_id)
 VALUES(gen_random_uuid(),NEW.tenant_id,typename,source,item,subject) ON CONFLICT(tenant_id,source_key) DO NOTHING;
 RETURN NEW;
END $$;
CREATE TRIGGER integration_task_events AFTER INSERT OR UPDATE ON ago_governed_tasks FOR EACH ROW EXECUTE FUNCTION ago_promote_integration_event();
CREATE TRIGGER integration_approval_events AFTER INSERT OR UPDATE ON ago_approval_requests FOR EACH ROW EXECUTE FUNCTION ago_promote_integration_event();
CREATE TRIGGER integration_report_events AFTER INSERT ON ago_analytics_reports FOR EACH ROW EXECUTE FUNCTION ago_promote_integration_event();
CREATE TRIGGER integration_settings_events AFTER INSERT ON ago_integration_settings FOR EACH ROW EXECUTE FUNCTION ago_promote_integration_event();
ALTER TABLE ago_oauth_codes ADD COLUMN client_digest text NOT NULL;
CREATE TABLE ago_oauth_throttle (
 peer_hash text NOT NULL,bucket bigint NOT NULL,hits int NOT NULL,
 PRIMARY KEY(peer_hash,bucket)
);
