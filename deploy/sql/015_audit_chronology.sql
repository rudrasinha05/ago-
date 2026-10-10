-- M6 audit chronology must not depend on PostgreSQL transaction-stable now().
-- Generated sequence gives an unambiguous insertion order even within one transaction.
ALTER TABLE ago_handoff_events
 ADD COLUMN event_order bigint GENERATED ALWAYS AS IDENTITY;
ALTER TABLE ago_calendar_audit
 ADD COLUMN event_order bigint GENERATED ALWAYS AS IDENTITY;
CREATE UNIQUE INDEX idx_ago_handoff_event_order ON ago_handoff_events(event_order);
CREATE UNIQUE INDEX idx_ago_calendar_event_order ON ago_calendar_audit(event_order);
ALTER TABLE ago_handoff_events ALTER COLUMN created_at SET DEFAULT clock_timestamp();
ALTER TABLE ago_calendar_audit ALTER COLUMN occurred_at SET DEFAULT clock_timestamp();
