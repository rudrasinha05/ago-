-- Continuous evidence-based company opportunity watch; shares AGO_POSTGRES_DSN.
-- Signals and campaigns are *records*, never claims of demand, publication or income.
CREATE TABLE ago_market_signals (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 source_name text NOT NULL CHECK(length(source_name) BETWEEN 3 AND 80),
 source_kind text NOT NULL CHECK(source_kind IN ('research','news','article')),
 source_url text NOT NULL CHECK(length(source_url) BETWEEN 12 AND 1200),
 url_digest char(64) NOT NULL,
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 8 AND 350),
 excerpt text NOT NULL DEFAULT '',
 potential_customer text NOT NULL DEFAULT 'To be validated',
 opportunity_score integer NOT NULL CHECK(opportunity_score BETWEEN 0 AND 100),
 score_basis text NOT NULL,
 evidence_level text NOT NULL DEFAULT 'unvalidated_signal'
   CHECK(evidence_level IN ('unvalidated_signal','customer_validated')),
 executive_owner_id uuid,
 approval_id uuid,
 review_status text NOT NULL DEFAULT 'discovered'
   CHECK(review_status IN ('discovered','shortlisted','discarded')),
 discovery_method text NOT NULL DEFAULT 'feed_heuristic'
   CHECK(discovery_method='feed_heuristic'),
 discovered_at timestamptz NOT NULL DEFAULT now(),
 nominated_at timestamptz,
 published_at timestamptz,
 UNIQUE(tenant_id,url_digest),
 FOREIGN KEY(tenant_id,executive_owner_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(approval_id) REFERENCES ago_approval_requests(id),
 CHECK(review_status<>'shortlisted' OR (approval_id IS NOT NULL AND nominated_at IS NOT NULL))
);
CREATE UNIQUE INDEX ago_market_signal_approval ON ago_market_signals(tenant_id,approval_id) WHERE approval_id IS NOT NULL;
CREATE INDEX ago_market_signals_queue ON ago_market_signals
 (tenant_id,review_status,opportunity_score DESC,discovered_at DESC);
CREATE TABLE ago_growth_scan_runs (
 id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 source_name text NOT NULL,
 outcome text NOT NULL CHECK(outcome IN('ok','degraded')),
 ingested_count integer NOT NULL DEFAULT 0 CHECK(ingested_count BETWEEN 0 AND 1000),
 checked_at timestamptz NOT NULL DEFAULT now(),
 -- No raw HTTP errors or tokens in logs.
 error_class text
);
CREATE INDEX ago_growth_scans_recent ON ago_growth_scan_runs(tenant_id,checked_at DESC);
CREATE TABLE ago_marketing_drafts (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 project_id uuid NOT NULL,
 platform text NOT NULL CHECK(platform IN ('linkedin','x','instagram','facebook')),
 draft_text text NOT NULL CHECK(length(draft_text) BETWEEN 20 AND 1500),
 stage text NOT NULL DEFAULT 'draft'
   CHECK(stage IN ('draft','approved','published','cancelled')),
 -- Importantly there is NO automatic publishing job and no credentials here.
 external_post_url text,
 approval_id uuid,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,project_id,platform),
 FOREIGN KEY(tenant_id,project_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(approval_id) REFERENCES ago_approval_requests(id),
 CHECK(stage<>'published' OR
       (approval_id IS NOT NULL AND external_post_url IS NOT NULL))
);
CREATE INDEX ago_marketing_queue ON ago_marketing_drafts(tenant_id,stage,created_at DESC);
