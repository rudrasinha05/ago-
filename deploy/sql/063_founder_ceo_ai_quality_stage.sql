-- AGO 063: Founder/CEO authority and staffed AI Quality stage.
-- Supersedes the historical reviewer-based trigger WITHOUT modifying audit history.
-- All delegations require the exact Founder-approved request and ACTIVE project.
-- An AI quality employee can verify work; it receives no human approval privilege.
CREATE OR REPLACE FUNCTION ago_guard_project_stage_delegation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE proposal record; authorized_founder boolean; active_scope boolean;
        eligible_ai boolean;
BEGIN
 SELECT d.approval_id,d.requester_id,a.action,a.status,a.reviewer_id
 INTO proposal
 FROM ago_project_stage_delegation_proposals d
 JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id AND a.id=d.approval_id
 WHERE d.tenant_id=NEW.tenant_id AND d.id=NEW.proposal_id;
 IF NOT FOUND OR proposal.action <> ('company:stage-delegation:' || NEW.proposal_id::text)
   OR proposal.status <> 'approved' OR proposal.reviewer_id IS NULL
 THEN RAISE EXCEPTION 'Exact founder decision required for stage assignment'; END IF;
 SELECT EXISTS(
   SELECT 1 FROM ago_users u
   JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
   JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
   WHERE u.tenant_id=NEW.tenant_id AND u.id=proposal.reviewer_id
     AND u.active AND e.kind='human' AND r.role='founder'
 ) INTO authorized_founder;
 IF NOT authorized_founder
 THEN RAISE EXCEPTION 'Only an active Founder may authorize this delegation'; END IF;
 SELECT EXISTS(
   SELECT 1 FROM ago_founder_intakes i
   JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
   JOIN ago_approval_requests a ON a.tenant_id=p.tenant_id AND a.id=p.approval_id
   WHERE i.tenant_id=NEW.tenant_id AND i.id=NEW.intake_id
     AND p.status='active' AND a.status='approved'
     AND a.reviewer_id=i.founder_id
 ) INTO active_scope;
 IF NOT active_scope
 THEN RAISE EXCEPTION 'Exact Founder-approved active project scope required'; END IF;
 SELECT EXISTS(
   SELECT 1 FROM ago_employees e
   WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id AND e.kind='ai'
     AND NOT EXISTS(
       SELECT 1 FROM ago_founder_project_lead m
       WHERE m.tenant_id=NEW.tenant_id AND m.intake_id=NEW.intake_id
         AND m.accountable_manager_id=e.id AND NEW.stage='quality'
     )
 ) INTO eligible_ai;
 IF NOT eligible_ai
 THEN RAISE EXCEPTION 'Actual AI specialist required; quality cannot review its own manager'; END IF;
 RETURN NEW;
END $$;
