-- AGO 064: CEO-owned routine staffing after the sole Founder project-scope approval.
-- This is a forward-only replacement of older reviewer-centric activation gates.
-- CEO board identity (AI) may sign ONLY a worker already named in that
-- exact active, Founder-approved project stage. No generic AI permission.
CREATE OR REPLACE FUNCTION ago_guard_project_stage_delegation()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE proposal record; founder_decider boolean; appointed_ceo boolean;
        approved_scope boolean; eligible_ai boolean;
BEGIN
 SELECT d.requester_id,a.action,a.status,a.reviewer_id
 INTO proposal
 FROM ago_project_stage_delegation_proposals d
 JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id
   AND a.id=d.approval_id
 WHERE d.tenant_id=NEW.tenant_id AND d.id=NEW.proposal_id;
 IF NOT FOUND OR proposal.action <> ('company:stage-delegation:'||NEW.proposal_id::text)
   OR proposal.status<>'approved' OR proposal.reviewer_id IS NULL
 THEN RAISE EXCEPTION 'Exact recorded stage authorization required'; END IF;

 SELECT EXISTS(
  SELECT 1 FROM ago_users u
  JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
  JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
  WHERE u.tenant_id=NEW.tenant_id AND u.id=proposal.reviewer_id
    AND u.active AND e.kind='human' AND r.role='founder'
 ) INTO founder_decider;
 SELECT EXISTS(
  SELECT 1 FROM ago_company_board_appointments b
  JOIN ago_employees ceo ON ceo.tenant_id=b.tenant_id
    AND ceo.id=b.employee_id AND ceo.kind='ai'
  JOIN ago_founder_intake_stages s ON s.tenant_id=b.tenant_id
    AND s.intake_id=NEW.intake_id AND s.stage=NEW.stage
  JOIN ago_founder_intakes i ON i.tenant_id=s.tenant_id AND i.id=s.intake_id
  JOIN ago_users founder ON founder.tenant_id=i.tenant_id
    AND founder.id=i.founder_id AND founder.active
  JOIN ago_user_roles fr ON fr.tenant_id=founder.tenant_id
    AND fr.user_id=founder.id AND fr.role='founder'
  WHERE b.tenant_id=NEW.tenant_id AND b.seat='Strategy & Vision'
    AND b.employee_id=proposal.reviewer_id
    AND proposal.requester_id=i.founder_id
    AND s.suggested_assignee_id=NEW.assignee_id
 ) INTO appointed_ceo;
 IF NOT (founder_decider OR appointed_ceo)
 THEN RAISE EXCEPTION 'Founder or exact scoped CEO staffing verification required'; END IF;

 SELECT EXISTS(
  SELECT 1 FROM ago_founder_intakes i
  JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
  JOIN ago_approval_requests a ON a.tenant_id=p.tenant_id AND a.id=p.approval_id
  WHERE i.tenant_id=NEW.tenant_id AND i.id=NEW.intake_id
    AND p.status='active' AND a.status='approved'
    AND a.reviewer_id=i.founder_id
 ) INTO approved_scope;
 IF NOT approved_scope
 THEN RAISE EXCEPTION 'Founder-approved active project scope required'; END IF;

 SELECT EXISTS(
  SELECT 1 FROM ago_employees e
  WHERE e.tenant_id=NEW.tenant_id AND e.id=NEW.assignee_id AND e.kind='ai'
    AND NOT EXISTS(
      SELECT 1 FROM ago_founder_project_lead lead
      WHERE lead.tenant_id=NEW.tenant_id AND lead.intake_id=NEW.intake_id
        AND NEW.stage='quality' AND lead.accountable_manager_id=e.id
    )
    AND NOT EXISTS(
      SELECT 1 FROM ago_founder_intake_stages s
      WHERE s.tenant_id=NEW.tenant_id AND s.intake_id=NEW.intake_id
        AND s.stage='implementation' AND NEW.stage='quality'
        AND s.suggested_assignee_id=e.id
    )
 ) INTO eligible_ai;
 IF NOT eligible_ai
 THEN RAISE EXCEPTION 'Verified company AI specialist required; QA cannot verify own implementation'; END IF;
 RETURN NEW;
END $$;
