-- AGO 076: the AI CEO fills a project stage that has no staffing at all.
--
-- Founder rule: unassigned roles are assigned by the AI leadership to their
-- existing employees; routine project decisions belong to the AI CEO.
-- Until now the CEO could confirm only a worker the project scope already
-- suggested, so a stage with NO suggestion (no fitting employee existed when
-- the project started) stopped the project for good.
--
-- Unchanged: Founder-approved active project required; AI employee only; the
-- CEO can never replace a recorded suggestion; no hiring, no task, no run.
-- Stricter: implementation and quality need different people in both
-- directions, including staffing approved after the original suggestion.
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
    -- 076: the CEO may also FILL a stage the approved scope left unstaffed.
    -- A recorded suggestion can still never be replaced by the CEO.
    AND (s.suggested_assignee_id=NEW.assignee_id OR s.suggested_assignee_id IS NULL)
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
    -- 076: builder and tester stay different people in BOTH directions, also
    -- against staffing that was approved later than the original suggestion.
    AND NOT EXISTS(
      SELECT 1 FROM ago_project_stage_delegation_activations other
      WHERE other.tenant_id=NEW.tenant_id AND other.intake_id=NEW.intake_id
        AND other.assignee_id=e.id
        AND ((NEW.stage='quality' AND other.stage='implementation')
          OR (NEW.stage='implementation' AND other.stage='quality'))
    )
 ) INTO eligible_ai;
 IF NOT eligible_ai
 THEN RAISE EXCEPTION 'Verified company AI specialist required; QA cannot verify own implementation'; END IF;
 RETURN NEW;
END $$;
