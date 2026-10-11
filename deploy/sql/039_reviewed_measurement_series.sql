-- Additive six-gate measurements. Existing sources/approvals remain immutable.
ALTER TABLE ago_enterprise_evidence DROP CONSTRAINT ago_enterprise_evidence_kind_check;
ALTER TABLE ago_enterprise_evidence ADD CONSTRAINT ago_enterprise_evidence_kind_check
 CHECK(kind IN ('operations','planning','competence','finance','diagnostics','twin_state',
 'forecast','calibration','experiment','intent','intent_result','lifecycle','experiment_registration',
 'experiment_measurement','financial_document','reconciliation','evolution_policy_audit',
 'economic_period','economic_study','economic_comparison','quality_subject','quality_study',
 'quality_sample','quality_report','metric_outcome','longitudinal_forecast','longitudinal_calibration'));

CREATE UNIQUE INDEX ago_quality_subject_version ON ago_enterprise_evidence
 (tenant_id,(payload->'intent'->>'dimension'),(payload->'intent'->>'entity_ref'),(payload->'intent'->>'version'))
 WHERE kind='quality_subject';
CREATE UNIQUE INDEX ago_quality_sample_identity ON ago_enterprise_evidence
 (tenant_id,(payload->'intent'->>'study_id'),(payload->'intent'->>'sample_ref'))
 WHERE kind='quality_sample';
CREATE UNIQUE INDEX ago_metric_outcome_period ON ago_enterprise_evidence
 (tenant_id,(payload->>'series_key'),(payload->'intent'->>'period_start'),(payload->'intent'->>'period_end'))
 WHERE kind='metric_outcome';

CREATE TABLE ago_economic_period_costs (
 tenant_id uuid NOT NULL,
 cost_id uuid NOT NULL,
 period_id uuid NOT NULL,
 PRIMARY KEY(tenant_id,cost_id),
 FOREIGN KEY(tenant_id,cost_id) REFERENCES ago_observed_costs(tenant_id,id),
 FOREIGN KEY(tenant_id,period_id) REFERENCES ago_enterprise_evidence(tenant_id,id)
);
CREATE TRIGGER ago_economic_period_cost_immutable BEFORE UPDATE OR DELETE
 ON ago_economic_period_costs FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
