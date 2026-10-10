-- Section 7: derived graph versions, semantic vectors and private object metadata.
-- Existing knowledge/audit records retain their immutable review rules.
CREATE INDEX IF NOT EXISTS idx_ago_knowledge_from ON ago_knowledge_edges(tenant_id,from_id,id);
CREATE INDEX IF NOT EXISTS idx_ago_knowledge_to ON ago_knowledge_edges(tenant_id,to_id,id);
CREATE TABLE ago_knowledge_versions (
    tenant_id uuid PRIMARY KEY REFERENCES ago_tenants(id) ON DELETE CASCADE,
    version bigint NOT NULL DEFAULT 0 CHECK(version >= 0)
);
INSERT INTO ago_knowledge_versions(tenant_id) SELECT id FROM ago_tenants;
CREATE FUNCTION ago_bump_knowledge_version() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO ago_knowledge_versions(tenant_id,version) VALUES(NEW.tenant_id,1)
    ON CONFLICT(tenant_id) DO UPDATE SET version=ago_knowledge_versions.version+1;
    RETURN NEW;
END $$;
CREATE TRIGGER ago_node_version AFTER INSERT OR UPDATE ON ago_knowledge_nodes
FOR EACH ROW EXECUTE FUNCTION ago_bump_knowledge_version();
CREATE TRIGGER ago_edge_version AFTER INSERT ON ago_knowledge_edges
FOR EACH ROW EXECUTE FUNCTION ago_bump_knowledge_version();

CREATE TABLE ago_semantic_vectors (
    tenant_id uuid NOT NULL,
    node_id uuid NOT NULL,
    model_id text NOT NULL CHECK(length(model_id) BETWEEN 1 AND 150),
    source_sha256 text NOT NULL CHECK(source_sha256 ~ '^[a-f0-9]{64}$'),
    embedding double precision[] NOT NULL,
    indexed_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY(tenant_id,model_id,node_id),
    FOREIGN KEY(tenant_id,node_id) REFERENCES ago_knowledge_nodes(tenant_id,id),
    CHECK(cardinality(embedding)=384 AND array_ndims(embedding)=1 AND array_length(embedding,1)=384
          AND array_lower(embedding,1)=1 AND array_position(embedding,NULL) IS NULL
          AND embedding<>array_fill(0::float8,ARRAY[384])
          AND NOT embedding && ARRAY['NaN'::float8,'Infinity'::float8,'-Infinity'::float8])
);
CREATE TABLE ago_document_objects (
    id uuid PRIMARY KEY,
    tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
    author_id uuid NOT NULL,
    filename text NOT NULL CHECK(length(filename) BETWEEN 1 AND 250),
    media_type text NOT NULL CHECK(media_type IN ('text/plain','application/pdf','application/octet-stream')),
    bytes integer NOT NULL CHECK(bytes BETWEEN 1 AND 524288),
    sha256 text NOT NULL CHECK(sha256 ~ '^[a-f0-9]{64}$'),
    status text NOT NULL DEFAULT 'active' CHECK(status IN ('active','expired')),
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    expired_at timestamptz,
    UNIQUE(tenant_id,id),
    FOREIGN KEY(tenant_id,author_id) REFERENCES ago_users(tenant_id,id),
    CHECK(expires_at > created_at),
    CHECK((status='active' AND expired_at IS NULL) OR (status='expired' AND expired_at IS NOT NULL))
);
CREATE INDEX idx_ago_objects_expiry ON ago_document_objects(tenant_id,status,expires_at,id);
CREATE FUNCTION ago_guard_document_metadata() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF TG_OP='DELETE' THEN RAISE EXCEPTION 'Object tombstones are retained'; END IF;
    IF ROW(NEW.id,NEW.tenant_id,NEW.author_id,NEW.filename,NEW.media_type,NEW.bytes,
           NEW.sha256,NEW.created_at,NEW.expires_at) IS DISTINCT FROM
       ROW(OLD.id,OLD.tenant_id,OLD.author_id,OLD.filename,OLD.media_type,OLD.bytes,
           OLD.sha256,OLD.created_at,OLD.expires_at)
       OR OLD.status<>'active' OR NEW.status<>'expired' OR NEW.expired_at IS NULL THEN
        RAISE EXCEPTION 'Only expiry of immutable object metadata is allowed';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER ago_object_metadata BEFORE UPDATE OR DELETE ON ago_document_objects
FOR EACH ROW EXECUTE FUNCTION ago_guard_document_metadata();
