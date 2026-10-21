-- Founder-owned strategy stays separate from independently reviewed workforce delegation.
-- Records proposals and activations; NEVER executes AI tasks, creates accounts,
-- grants roles, publishes or pays. All decisions are tenant scoped.
CREATE TABLE ago_project_stage_delegation_proposals (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 intake_id uuid NOT NULL,
 stage text NOT NULL CHECK (stage IN
    ('discovery','architecture','implementation','quality','release')),
 assignee_id uuid NOT NULL,
 requester_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,id),
 UNIQUE(tenant_id,id,intake_id,stage,assignee_id),
 UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY(tenant_id,assignee_id) REFERENCES ago_employees(tenant_id,id),
 FOREIGN KEY(tenant_id,requester_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id)
);
CREATE TRIGGER ago_stage_delegation_proposals_append_only
 BEFORE UPDATE OR DELETE ON ago_project_stage_delegation_proposals
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE TABLE ago_project_stage_delegation_activations (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 proposal_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 stage text NOT NULL,
 assignee_id uuid NOT NULL,
 applied_by uuid NOT NULL,
 applied_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(tenant_id,intake_id,stage),
 FOREIGN KEY(tenant_id,proposal_id,intake_id,stage,assignee_id)
    REFERENCES ago_project_stage_delegation_proposals
       (tenant_id,id,intake_id,stage,assignee_id),
 FOREIGN KEY(tenant_id,applied_by) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_delegation_assignments_worker_idx
 ON ago_project_stage_delegation_activations(tenant_id,assignee_id,applied_at DESC);
CREATE TRIGGER ago_stage_delegation_activations_append_only
 BEFORE UPDATE OR DELETE ON ago_project_stage_delegation_activations
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

-- A privileged SQL caller cannot forge a delegation without the exact
-- independently approved operational request and active founder strategy.
CREATE FUNCTION ago_guard_project_stage_delegation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE proposal record; reviewer_is_independent boolean; plan_activated boolean;
        worker_eligible boolean;
BEGIN
 SELECT d.approval_id,d.requester_id,a.action,a.status,a.reviewer_id
 INTO proposal
 FROM ago_project_stage_delegation_proposals d
 JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id AND a.id=d.approval_id
 WHERE d.tenant_id=NEW.tenant_id AND d.id=NEW.proposal_id;
 IF NOT FOUND
 OR proposal.action <> ('company:stage-delegation:' || NEW.proposal_id::text)
 OR proposal.status <> 'approved'
 OR proposal.reviewer_id IS NULL
 OR proposal.reviewer_id=proposal.requester_id
 THEN RAISE EXCEPTION 'Exact independent operational approval required'; END IF;
 SELECT EXISTS(
  SELECT 1 FROM ago_users u JOIN ago_employees e
    ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
  JOIN ago_user_roles r
    ON r.tenant_id=u.tenant_id AND r.user_id=u.id AND r.role='reviewer'
  WHERE u.tenant_id=NEW.tenant_id AND u.id=proposal.reviewer_id AND u.active
 ) INTO reviewer_is_independent;
 IF NOT reviewer_is_independent
 THEN RAISE EXCEPTION 'Active independent human reviewer required'; END IF;
 SELECT EXISTS(
   SELECT 1 FROM ago_founder_intakes i JOIN ago_strategy_plans p
    ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
   WHERE i.tenant_id=NEW.tenant_id AND i.id=NEW.intake_id AND p.status='active'
 ) INTO plan_activated;
 IF NOT plan_activated
 THEN RAISE EXCEPTION 'Founder-approved active project plan required'; END IF;
 -- Independent QA can never be assigned to the person who reviewed their
 -- own staffing request. Execution workers must be real tenant-owned AI staff.
 SELECT EXISTS(
  SELECT 1 FROM ago_employees e
  LEFT JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
  LEFT JOIN ago_user_roles r ON r.tenant_id=e.tenant_id
    AND r.user_id=e.id AND r.role='reviewer'
  WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id
    AND (
      (NEW.stage='quality' AND e.kind='human' AND r.role='reviewer'
       AND proposal.reviewer_id <> NEW.assignee_id)
      OR (NEW.stage<>'quality' AND e.kind='ai')
    )
 ) INTO worker_eligible;
 IF NOT worker_eligible
 THEN RAISE EXCEPTION 'Ineligible worker or reviewer conflict'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_guard_project_stage_delegation_insert
 BEFORE INSERT ON ago_project_stage_delegation_activations
 FOR EACH ROW EXECUTE FUNCTION ago_guard_project_stage_delegation();
