-- A market signal can create one founder-authorized governed PROJECT DRAFT.
-- Does not grant task execution, ad spending, publishing or customer contact.
ALTER TABLE ago_market_signals
  ADD CONSTRAINT ago_market_signal_tenant_id UNIQUE (tenant_id,id);

CREATE TABLE ago_market_signal_project_links (
 tenant_id uuid NOT NULL REFERENCES ago_tenants(id) ON DELETE CASCADE,
 signal_id uuid NOT NULL,
 intake_id uuid NOT NULL,
 approved_at timestamptz NOT NULL DEFAULT now(),
 linked_by uuid NOT NULL,
 approval_id uuid NOT NULL,
 PRIMARY KEY (tenant_id,signal_id),
 UNIQUE(tenant_id,intake_id),
 FOREIGN KEY (tenant_id,signal_id) REFERENCES ago_market_signals(tenant_id,id),
 FOREIGN KEY (tenant_id,intake_id) REFERENCES ago_founder_intakes(tenant_id,id),
 FOREIGN KEY (tenant_id,linked_by) REFERENCES ago_users(tenant_id,id),
 FOREIGN KEY (approval_id) REFERENCES ago_approval_requests(id)
);
CREATE INDEX ago_market_signal_project_projects
 ON ago_market_signal_project_links(tenant_id,intake_id);
CREATE TRIGGER ago_market_signal_links_append_only BEFORE UPDATE OR DELETE
 ON ago_market_signal_project_links FOR EACH ROW
 EXECUTE FUNCTION ago_protect_append_only();

-- Re-validate founder authorization even for privileged SQL writes.
CREATE FUNCTION ago_guard_signal_to_project() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approved record; founder_human boolean;
BEGIN
 SELECT s.id,s.approval_id,s.review_status,s.executive_owner_id,a.action,a.status,
        a.requester_id,a.reviewer_id INTO approved
 FROM ago_market_signals s
 JOIN ago_approval_requests a ON a.tenant_id=s.tenant_id AND a.id=s.approval_id
 WHERE s.tenant_id=NEW.tenant_id AND s.id=NEW.signal_id;
 IF NOT FOUND OR approved.review_status<>'shortlisted'
  OR approved.approval_id<>NEW.approval_id
  OR approved.action<>('company:market-signal:'||NEW.signal_id::text)
  OR approved.requester_id<>approved.executive_owner_id
  OR approved.status<>'approved' OR approved.reviewer_id<>NEW.linked_by
 THEN RAISE EXCEPTION 'Exact founder-approved source signal required'; END IF;
 SELECT EXISTS(
  SELECT 1 FROM ago_users u
  JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
  JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
  WHERE u.id=NEW.linked_by AND u.tenant_id=NEW.tenant_id
    AND u.active AND r.role='founder'
 ) INTO founder_human;
 IF NOT founder_human THEN
  RAISE EXCEPTION 'Only original authorizing human founder can promote this signal';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER ago_signal_to_project_guard BEFORE INSERT ON ago_market_signal_project_links
 FOR EACH ROW EXECUTE FUNCTION ago_guard_signal_to_project();
