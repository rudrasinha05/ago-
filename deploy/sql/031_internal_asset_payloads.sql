-- Section 25: local-first immutable internal asset bytes (1 MiB maximum).
-- No cloud account, no runtime execution and no automatic paid marketplace.
CREATE TABLE ago_marketplace_payloads (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 asset_id uuid NOT NULL,
 publisher_id uuid NOT NULL,
 content_type text NOT NULL CHECK(content_type IN (
   'text/plain','text/markdown','application/json','application/octet-stream'
 )),
 payload bytea NOT NULL CHECK(octet_length(payload) BETWEEN 1 AND 1048576),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,asset_id),
 FOREIGN KEY(tenant_id,asset_id) REFERENCES ago_marketplace_assets(tenant_id,id),
 FOREIGN KEY(tenant_id,publisher_id) REFERENCES ago_users(tenant_id,id)
);
CREATE FUNCTION ago_marketplace_payload_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE owner record;
BEGIN
 SELECT publisher_id,status,digest INTO owner FROM ago_marketplace_assets
 WHERE tenant_id=NEW.tenant_id AND id=NEW.asset_id FOR UPDATE;
 IF NOT FOUND OR owner.status <> 'draft' OR owner.publisher_id<>NEW.publisher_id
 OR NEW.digest IS DISTINCT FROM owner.digest
 OR encode(sha256(NEW.payload),'hex') IS DISTINCT FROM owner.digest THEN
   RAISE EXCEPTION 'Asset content must be uploaded by draft publisher and match fixed digest';
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_marketplace_payload_insert_guard BEFORE INSERT ON ago_marketplace_payloads
 FOR EACH ROW EXECUTE FUNCTION ago_marketplace_payload_guard();
CREATE TRIGGER ago_marketplace_payload_immutable BEFORE UPDATE OR DELETE ON ago_marketplace_payloads
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

-- Backward-compatible metadata-only listings are still valid. Assets explicitly
-- marked as reusable payloads must contain independently verifiable content.
CREATE FUNCTION ago_marketplace_required_payload() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF TG_TABLE_NAME='ago_marketplace_assets' THEN
   IF NEW.status='published' AND NEW.manifest->>'payload_required'='true' AND
      NOT EXISTS(SELECT 1 FROM ago_marketplace_payloads p
      WHERE p.tenant_id=NEW.tenant_id AND p.asset_id=NEW.id) THEN
     RAISE EXCEPTION 'Reusable asset needs checksum-verified content before publishing';
   END IF;
 ELSE
   IF EXISTS(SELECT 1 FROM ago_marketplace_assets a
      WHERE a.tenant_id=NEW.tenant_id AND a.id=NEW.asset_id
      AND a.manifest->>'payload_required'='true'
      AND NOT EXISTS(SELECT 1 FROM ago_marketplace_payloads p
      WHERE p.tenant_id=a.tenant_id AND p.asset_id=a.id)) THEN
     RAISE EXCEPTION 'Cannot consume a missing reusable payload';
   END IF;
 END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_marketplace_publish_requires_payload
 BEFORE UPDATE ON ago_marketplace_assets FOR EACH ROW
 EXECUTE FUNCTION ago_marketplace_required_payload();
CREATE TRIGGER ago_marketplace_consume_requires_payload
 BEFORE INSERT ON ago_asset_consumptions FOR EACH ROW
 EXECUTE FUNCTION ago_marketplace_required_payload();
