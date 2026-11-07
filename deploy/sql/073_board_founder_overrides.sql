-- Founder override of a Board denial (Founder rule, 2026-11-07).
-- When the AI CEO (Strategy & Vision) and AI CTO (Technology Oversight) both
-- approved, a denial or unclear vote from another Board seat (Finance,
-- Risk, Quality) is shown to the Founder with who denied and why. If the
-- Founder allows the project, that seat's later votes in THIS project are
-- recorded as advice and no longer stop the AI team. CEO/CTO denials are
-- never overridable here. One immutable row per project and seat.
CREATE TABLE ago_board_founder_overrides (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 seat text NOT NULL CHECK (seat IN ('Finance & Budget','Risk & Compliance','Quality & Release')),
 denied_task_id uuid NOT NULL,
 denial_vote text NOT NULL CHECK (denial_vote IN ('deny','unverified')),
 denial_reason text NOT NULL DEFAULT '' CHECK (length(denial_reason) <= 500),
 founder_id uuid NOT NULL,
 reason text NOT NULL CHECK (length(trim(reason)) BETWEEN 1 AND 500),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,intake_id,seat),
 FOREIGN KEY (tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,denied_task_id) REFERENCES ago_governed_tasks(tenant_id,id),
 FOREIGN KEY (tenant_id,founder_id) REFERENCES ago_users(tenant_id,id)
);
CREATE TRIGGER ago_board_founder_overrides_immutable
 BEFORE UPDATE OR DELETE ON ago_board_founder_overrides
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();
