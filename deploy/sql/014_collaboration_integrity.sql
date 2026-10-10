-- M6 integrity hardening. All guards are additive migrations.
ALTER TABLE ago_knowledge_nodes ADD CONSTRAINT ago_knowledge_review_reason_required
 CHECK (status='pending' OR
        (review_note IS NOT NULL AND length(trim(review_note)) > 0));

CREATE TABLE ago_calendar_audit (
 id uuid PRIMARY KEY,
 tenant_id uuid NOT NULL,
 event_id uuid NOT NULL,
 actor_id uuid NOT NULL,
 event text NOT NULL CHECK (event IN ('scheduled','cancelled','accepted','declined')),
 note text NOT NULL CHECK (length(trim(note)) > 0),
 occurred_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY (tenant_id,event_id) REFERENCES ago_calendar_events(tenant_id,id),
 FOREIGN KEY (tenant_id,actor_id) REFERENCES ago_users(tenant_id,id)
);
CREATE INDEX idx_ago_calendar_audit ON ago_calendar_audit(tenant_id,event_id,occurred_at);
CREATE TRIGGER ago_calendar_audit_protect BEFORE UPDATE OR DELETE ON ago_calendar_audit
 FOR EACH ROW EXECUTE FUNCTION ago_protect_append_only();

CREATE OR REPLACE FUNCTION ago_guard_handoff() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE'
  AND (
      (OLD.status='requested' AND NEW.status IN ('accepted','rejected'))
      OR (OLD.status='accepted' AND NEW.status='completed'
          AND OLD.receiver_actor_id=NEW.receiver_actor_id)
  )
  AND NEW.receiver_actor_id IS NOT NULL
  AND NEW.conclusion IS NOT NULL AND length(trim(NEW.conclusion)) > 0
  AND (OLD.id,OLD.tenant_id,OLD.requester_id,OLD.sender_department_id,
       OLD.receiver_department_id,OLD.assignee_id,OLD.title,OLD.brief,
       OLD.operation_key,OLD.created_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.requester_id,NEW.sender_department_id,
       NEW.receiver_department_id,NEW.assignee_id,NEW.title,NEW.brief,
       NEW.operation_key,NEW.created_at)
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Handoff history is write-protected';
END;
$$;
CREATE TRIGGER ago_handoffs_integrity BEFORE UPDATE OR DELETE ON ago_handoffs
 FOR EACH ROW EXECUTE FUNCTION ago_guard_handoff();

CREATE OR REPLACE FUNCTION ago_guard_calendar() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
 IF TG_OP='UPDATE'
  AND OLD.status='scheduled' AND NEW.status='cancelled'
  AND (OLD.id,OLD.tenant_id,OLD.creator_id,OLD.title,OLD.detail,
       OLD.starts_at,OLD.ends_at,OLD.visibility,OLD.operation_key,
       OLD.goal_id,OLD.task_id,OLD.created_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.creator_id,NEW.title,NEW.detail,
       NEW.starts_at,NEW.ends_at,NEW.visibility,NEW.operation_key,
       NEW.goal_id,NEW.task_id,NEW.created_at)
 THEN RETURN NEW; END IF;
 RAISE EXCEPTION 'Calendar events are append-oriented';
END;
$$;
CREATE TRIGGER ago_calendar_integrity BEFORE UPDATE OR DELETE ON ago_calendar_events
 FOR EACH ROW EXECUTE FUNCTION ago_guard_calendar();

CREATE OR REPLACE FUNCTION ago_guard_council_motion() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
 yes_count bigint;
 no_count bigint;
 approval_ok boolean;
BEGIN
 IF TG_OP='UPDATE' AND OLD.status='open'
  AND NEW.status IN ('passed','rejected')
  AND NEW.finalized_at IS NOT NULL
  AND (OLD.id,OLD.tenant_id,OLD.proposer_id,OLD.title,OLD.rationale,
       OLD.required_votes,OLD.approval_id,OLD.created_at) IS NOT DISTINCT FROM
      (NEW.id,NEW.tenant_id,NEW.proposer_id,NEW.title,NEW.rationale,
       NEW.required_votes,NEW.approval_id,NEW.created_at)
 THEN
   SELECT count(*) FILTER (WHERE vote='yes'),
          count(*) FILTER (WHERE vote='no')
   INTO yes_count,no_count FROM ago_council_votes
   WHERE tenant_id=NEW.tenant_id AND motion_id=NEW.id;
   IF NEW.status='rejected' AND no_count>0 THEN RETURN NEW; END IF;
   IF NEW.status='passed' AND no_count=0 AND yes_count>=NEW.required_votes THEN
     SELECT EXISTS(
       SELECT 1 FROM ago_approval_requests
       WHERE tenant_id=NEW.tenant_id AND id=NEW.approval_id
         AND status='approved'
         AND action='council:pass:' || NEW.id::text
     ) INTO approval_ok;
     IF approval_ok THEN RETURN NEW; END IF;
   END IF;
 END IF;
 RAISE EXCEPTION 'Council requires immutable quorum and independent approval';
END;
$$;
DROP TRIGGER ago_council_motions_protect ON ago_council_motions;
CREATE TRIGGER ago_council_motion_integrity BEFORE UPDATE OR DELETE
 ON ago_council_motions FOR EACH ROW EXECUTE FUNCTION ago_guard_council_motion();
