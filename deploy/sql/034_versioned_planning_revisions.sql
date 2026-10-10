-- Section 23: immutable, exact-payload, reviewed planning revisions.
-- Existing approved plans/DA​G tasks retain their history. Replanning is
-- versioned and does not authorize tasks or change original step approvals.
CREATE TABLE ago_horizon_replan_intents (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 horizon_plan_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 approval_id uuid NOT NULL,
 base_revision int NOT NULL CHECK(base_revision>0),
 title text NOT NULL CHECK(length(trim(title)) BETWEEN 1 AND 300),
 starts_at timestamptz NOT NULL,
 ends_at timestamptz NOT NULL,
 budget_ceiling numeric(20,6) NOT NULL CHECK(budget_ceiling>=0),
 evidence_ref text NOT NULL CHECK(length(trim(evidence_ref)) BETWEEN 1 AND 1024),
 rationale text NOT NULL CHECK(length(trim(rationale)) BETWEEN 1 AND 2000),
 canonical_payload text NOT NULL CHECK(length(canonical_payload) BETWEEN 20 AND 6000),
 digest text NOT NULL CHECK(digest ~ '^[a-f0-9]{64}$'),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,horizon_plan_id) REFERENCES ago_horizon_plans(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 CHECK(starts_at<ends_at)
);
CREATE TABLE ago_horizon_plan_revisions (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 horizon_plan_id uuid NOT NULL,
 intent_id uuid NOT NULL,
 revision int NOT NULL CHECK(revision>=2),
 approval_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 UNIQUE(tenant_id,id), UNIQUE(tenant_id,horizon_plan_id,revision),
 UNIQUE(tenant_id,intent_id), UNIQUE(tenant_id,approval_id),
 FOREIGN KEY(tenant_id,horizon_plan_id) REFERENCES ago_horizon_plans(tenant_id,id),
 FOREIGN KEY(tenant_id,intent_id) REFERENCES ago_horizon_replan_intents(tenant_id,id),
 FOREIGN KEY(tenant_id,approval_id) REFERENCES ago_approval_requests(tenant_id,id),
 FOREIGN KEY(tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX ago_horizon_revisions_latest ON ago_horizon_plan_revisions
 (tenant_id,horizon_plan_id,revision DESC);

CREATE FUNCTION ago_horizon_replan_intent_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE a record;
BEGIN
 SELECT action,status,requester_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF NOT FOUND OR a.status IS DISTINCT FROM 'pending'
 OR a.requester_id IS DISTINCT FROM NEW.actor_id
 OR a.action IS DISTINCT FROM ('enterprise:plan-revise:'||
     NEW.horizon_plan_id::text||':'||NEW.digest)
 OR NEW.digest IS DISTINCT FROM encode(sha256(convert_to(NEW.canonical_payload,'UTF8')),'hex')
 THEN RAISE EXCEPTION 'Immutable pending plan revision review required'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_horizon_replan_intent_review BEFORE INSERT ON ago_horizon_replan_intents
 FOR EACH ROW EXECUTE FUNCTION ago_horizon_replan_intent_guard();
CREATE TRIGGER ago_horizon_replan_intent_immutable BEFORE UPDATE OR DELETE ON ago_horizon_replan_intents
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();

CREATE FUNCTION ago_horizon_revision_guard() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE p record; a record; last_revision int; ancestor record; inherited record;
BEGIN
 SELECT * INTO p FROM ago_horizon_replan_intents
 WHERE tenant_id=NEW.tenant_id AND id=NEW.intent_id;
 SELECT action,status,requester_id,reviewer_id INTO a FROM ago_approval_requests
 WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id;
 IF p.id IS NULL OR p.horizon_plan_id<>NEW.horizon_plan_id OR
    p.approval_id<>NEW.approval_id OR p.actor_id<>NEW.actor_id OR
    a.status IS DISTINCT FROM 'approved' OR
    a.requester_id IS DISTINCT FROM NEW.actor_id OR
    a.reviewer_id IS NULL OR a.reviewer_id=a.requester_id OR
    a.action IS DISTINCT FROM ('enterprise:plan-revise:'||
       NEW.horizon_plan_id::text||':'||p.digest)
 THEN RAISE EXCEPTION 'Independent exact plan revision approval required'; END IF;
 SELECT coalesce(max(revision),1) INTO last_revision
 FROM ago_horizon_plan_revisions
 WHERE tenant_id=NEW.tenant_id AND horizon_plan_id=NEW.horizon_plan_id;
 IF NEW.revision<>p.base_revision+1 OR last_revision<>p.base_revision THEN
   RAISE EXCEPTION 'Stale plan revision: independent re-review required'; END IF;
 SELECT * INTO ancestor FROM ago_horizon_plans
 WHERE tenant_id=NEW.tenant_id AND id=NEW.horizon_plan_id;
 IF ancestor.id IS NULL THEN RAISE EXCEPTION 'Plan missing'; END IF;
 IF ancestor.parent_id IS NOT NULL THEN
  SELECT h.starts_at,h.ends_at,h.budget_ceiling INTO inherited
  FROM ago_horizon_plans h
  WHERE h.tenant_id=NEW.tenant_id AND h.id=ancestor.parent_id;
  SELECT r_int.starts_at,r_int.ends_at,r_int.budget_ceiling INTO inherited
  FROM ago_horizon_plan_revisions rv
  JOIN ago_horizon_replan_intents r_int
    ON r_int.tenant_id=rv.tenant_id AND r_int.id=rv.intent_id
  WHERE rv.tenant_id=NEW.tenant_id AND rv.horizon_plan_id=ancestor.parent_id
  ORDER BY rv.revision DESC LIMIT 1;
  -- If no parent revision exists, retain the frozen original parent window.
  IF NOT FOUND THEN
    SELECT starts_at,ends_at,budget_ceiling INTO inherited
    FROM ago_horizon_plans WHERE tenant_id=NEW.tenant_id AND id=ancestor.parent_id;
  END IF;
  IF p.starts_at<inherited.starts_at OR p.ends_at>inherited.ends_at OR
     p.budget_ceiling>inherited.budget_ceiling THEN
    RAISE EXCEPTION 'Revised horizon outside approved parent budget/calendar';
  END IF;
 END IF;
 -- Existing child windows, budgets and executed-task links cannot be invalidated.
 IF EXISTS (
   SELECT 1 FROM ago_horizon_plans child
   LEFT JOIN LATERAL (
      SELECT ri.starts_at,ri.ends_at,ri.budget_ceiling
      FROM ago_horizon_plan_revisions rv JOIN ago_horizon_replan_intents ri
        ON ri.tenant_id=rv.tenant_id AND ri.id=rv.intent_id
      WHERE rv.tenant_id=child.tenant_id AND rv.horizon_plan_id=child.id
      ORDER BY rv.revision DESC LIMIT 1
   ) c ON true
   WHERE child.tenant_id=NEW.tenant_id AND child.parent_id=NEW.horizon_plan_id
   AND (coalesce(c.starts_at,child.starts_at)<p.starts_at
    OR coalesce(c.ends_at,child.ends_at)>p.ends_at
    OR coalesce(c.budget_ceiling,child.budget_ceiling)>p.budget_ceiling)
 ) THEN RAISE EXCEPTION 'Cannot orphan approved descendant horizons'; END IF;
 IF EXISTS (
   SELECT 1 FROM ago_horizon_task_links l
   JOIN ago_governed_tasks t ON t.tenant_id=l.tenant_id AND t.id=l.task_id
   WHERE l.tenant_id=NEW.tenant_id AND l.horizon_plan_id=NEW.horizon_plan_id
   AND (t.created_at<p.starts_at OR t.created_at>p.ends_at)
 ) THEN RAISE EXCEPTION 'Cannot orphan previously approved execution evidence'; END IF;
 RETURN NEW;
END;
$$;
CREATE TRIGGER ago_horizon_revision_review BEFORE INSERT ON ago_horizon_plan_revisions
 FOR EACH ROW EXECUTE FUNCTION ago_horizon_revision_guard();
CREATE TRIGGER ago_horizon_revision_immutable BEFORE UPDATE OR DELETE ON ago_horizon_plan_revisions
 FOR EACH ROW EXECUTE FUNCTION ago_enterprise_append_only();
