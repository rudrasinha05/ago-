-- M6 executive council motions are advisory; no automatic side effects.
CREATE TABLE ago_council_motions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 proposer_id uuid NOT NULL,
 title text NOT NULL CHECK (length(trim(title)) BETWEEN 1 AND 250),
 rationale text NOT NULL CHECK (length(trim(rationale)) BETWEEN 1 AND 6000),
 required_votes integer NOT NULL CHECK (required_votes BETWEEN 2 AND 10),
 status text NOT NULL DEFAULT 'open' CHECK (status IN ('open','passed','rejected')),
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 finalized_at timestamptz,
 UNIQUE (tenant_id,id),
 UNIQUE (tenant_id,approval_id),
 FOREIGN KEY (tenant_id,proposer_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK ((status='open' AND finalized_at IS NULL) OR
        (status<>'open' AND finalized_at IS NOT NULL))
);
CREATE INDEX idx_ago_council_status ON ago_council_motions(tenant_id,status,created_at);
CREATE TABLE ago_council_votes (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 motion_id uuid NOT NULL,
 voter_id uuid NOT NULL,
 vote text NOT NULL CHECK (vote IN ('yes','no')),
 reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 3000),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE (tenant_id,motion_id,voter_id),
 FOREIGN KEY (tenant_id,motion_id) REFERENCES ago_council_motions(tenant_id,id),
 FOREIGN KEY (tenant_id,voter_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX idx_ago_council_votes ON ago_council_votes(tenant_id,motion_id);
CREATE TRIGGER ago_council_votes_protect BEFORE UPDATE OR DELETE ON ago_council_votes
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
CREATE TRIGGER ago_council_motions_protect AFTER DELETE ON ago_council_motions
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
