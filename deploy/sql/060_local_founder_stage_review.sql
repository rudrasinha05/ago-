-- Add a deliberately narrow local sole-human-founder review path to stage delegation.
-- Previous immutable 058 migration remains unchanged. Human reviewer approvals still work.
-- API is the only normal writer of approvals; it enforces localhost opt-in, active
-- founder authentication, tenant scope, reason and atomic decision audit.
CREATE OR REPLACE FUNCTION ago_guard_project_stage_delegation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE proposal record; reviewer_is_independent boolean; founder_solo boolean;
        plan_activated boolean; worker_eligible boolean;
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
 THEN RAISE EXCEPTION 'Exact authorized operational approval required'; END IF;

 SELECT EXISTS(
  SELECT 1 FROM ago_users u JOIN ago_employees e
    ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
  JOIN ago_user_roles r
    ON r.tenant_id=u.tenant_id AND r.user_id=u.id AND r.role='reviewer'
  WHERE u.tenant_id=NEW.tenant_id AND u.id=proposal.reviewer_id AND u.active
    AND proposal.reviewer_id<>proposal.requester_id
 ) INTO reviewer_is_independent;

 -- Self-approved operational requests can arise only from the explicitly
 -- opted-in, active human founder application gateway (never from a Board label).
 -- Verify the durable actor and absence of a second authorized human reviewer
 -- again at stage activation. This is NOT a replacement for task QA verdicts.
 SELECT (
  proposal.reviewer_id=proposal.requester_id
  AND EXISTS(
    SELECT 1 FROM ago_users u
    JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
    JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
    WHERE u.tenant_id=NEW.tenant_id AND u.id=proposal.reviewer_id
      AND u.active AND e.kind='human' AND r.role='founder'
  )
  AND NOT EXISTS(
    SELECT 1 FROM ago_users u
    JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
    JOIN ago_role_permissions p ON p.tenant_id=r.tenant_id AND p.role=r.role
    JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
    WHERE u.tenant_id=NEW.tenant_id AND u.id<>proposal.reviewer_id
      AND u.active AND e.kind='human' AND p.permission='approval:decide'
  )
 ) INTO founder_solo;

 IF NOT (reviewer_is_independent OR founder_solo)
 THEN RAISE EXCEPTION 'Active independent human reviewer or qualified sole founder required'; END IF;

 SELECT EXISTS(
   SELECT 1 FROM ago_founder_intakes i JOIN ago_strategy_plans p
    ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
   WHERE i.tenant_id=NEW.tenant_id AND i.id=NEW.intake_id AND p.status='active'
 ) INTO plan_activated;
 IF NOT plan_activated
 THEN RAISE EXCEPTION 'Founder-approved active project plan required'; END IF;

 SELECT EXISTS(
  SELECT 1 FROM ago_employees e
  LEFT JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
  LEFT JOIN ago_user_roles r ON r.tenant_id=e.tenant_id
    AND r.user_id=e.id AND r.role='reviewer'
  WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id
    AND (
      (NEW.stage='quality' AND e.kind='human'
        AND (
          (reviewer_is_independent AND r.role='reviewer'
           AND proposal.reviewer_id<>NEW.assignee_id)
          OR
          (founder_solo AND e.id=proposal.reviewer_id
           AND NOT EXISTS(
             SELECT 1 FROM ago_founder_project_lead lead
             WHERE lead.tenant_id=NEW.tenant_id AND lead.intake_id=NEW.intake_id
               AND lead.accountable_manager_id=e.id
           ))
        ))
      OR (NEW.stage<>'quality' AND e.kind='ai')
    )
 ) INTO worker_eligible;
 IF NOT worker_eligible
 THEN RAISE EXCEPTION 'Ineligible stage assignee or QA conflict'; END IF;
 RETURN NEW;
END $$;
