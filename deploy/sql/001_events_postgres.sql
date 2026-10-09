-- PostgreSQL 15+; execute once before using PostgresEventStore.
CREATE TABLE IF NOT EXISTS event_outbox (
    id uuid PRIMARY KEY,
    name text NOT NULL,
    payload jsonb NOT NULL,
    occurred_at timestamptz NOT NULL,
    correlation_id text,
    status text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending','leased','delivered','dead')),
    attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    available_at timestamptz NOT NULL DEFAULT now(),
    lease_owner text,
    last_error text
);
CREATE INDEX IF NOT EXISTS idx_event_outbox_due
    ON event_outbox(available_at, id)
    WHERE status IN ('pending', 'leased');
CREATE TABLE IF NOT EXISTS event_inbox (
    consumer text NOT NULL,
    event_id uuid NOT NULL,
    handled_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (consumer, event_id)
);
