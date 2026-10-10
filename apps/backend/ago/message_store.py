"""Caller-owned PostgreSQL versioned inbox/outbox with fenced ordered leases."""
from __future__ import annotations

import json
from collections.abc import Callable
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.message_contracts import MessageEnvelope
from ago.security import Principal
from ago.security_controls import SecurityControls


class MessageStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def publish(self, *, actor: Principal, kind: str, name: str, payload: dict,
                operation_key: str, ordering_key: str = 'default',
                correlation_id: str | None = None) -> dict:
        envelope = MessageEnvelope(kind, name, actor.tenant_id, actor.subject,
            correlation_id or str(uuid4()), operation_key, ordering_key,
            json.dumps(payload, sort_keys=True, allow_nan=False))
        controls = self.repositories.resolve(SecurityControls)
        with self.db.transaction():
            if not controls.permitted(actor, 'messages:write', actor.tenant_id):
                raise PermissionError('Message publication permission required')
            self.db.execute('SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE', (actor.tenant_id,))
            existing = self.db.execute(
                'SELECT id,body_sha256 FROM event_outbox WHERE tenant_id=%s AND operation_key=%s',
                (actor.tenant_id, operation_key)).fetchone()
            if existing:
                if existing['body_sha256'] != envelope.digest():
                    raise ValueError('Idempotency key already has different content')
                return {'id': str(existing['id']), 'duplicate': True}
            if kind == 'approval':
                request = self.db.execute(
                    """SELECT requester_id,status FROM ago_approval_requests
                       WHERE tenant_id=%s AND id=%s FOR SHARE""",
                    (actor.tenant_id, payload['request_id'])).fetchone()
                if not request or request['status'] != 'pending' or str(request['requester_id']) != actor.subject:
                    raise PermissionError('Own same-tenant pending approval request required')
            identifier = str(uuid4())
            self.db.execute(
                """INSERT INTO event_outbox(id,name,payload,occurred_at,correlation_id,
                   tenant_id,actor_id,message_kind,operation_key,ordering_key,body_sha256)
                   VALUES(%s,%s,%s::jsonb,now(),%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, name, envelope.payload_json, envelope.correlation_id,
                 actor.tenant_id, actor.subject, kind, operation_key, ordering_key, envelope.digest()))
            controls.audit('message.publish', 'accepted', tenant_id=actor.tenant_id,
                           actor_id=actor.subject, metadata={'message_id': identifier, 'kind': kind})
        return {'id': identifier, 'duplicate': False}

    def inspect(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        UUID(tenant_id)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Invalid message inspection limit')
        return [dict(row) for row in self.db.execute(
            """SELECT id,name,message_kind,correlation_id,ordering_key,sequence,status,
                      attempts,cycle_attempts,replay_count,available_at,last_error
               FROM event_outbox WHERE tenant_id=%s AND message_kind IS NOT NULL
               ORDER BY sequence DESC LIMIT %s""", (tenant_id, limit)).fetchall()]

    def metrics(self, *, tenant_id: str) -> dict:
        UUID(tenant_id)
        rows = self.db.execute(
            """SELECT status,count(*) AS count,min(occurred_at) AS oldest,
                      max(attempts) AS max_attempts
               FROM event_outbox WHERE tenant_id=%s AND message_kind IS NOT NULL
               GROUP BY status ORDER BY status""", (tenant_id,)).fetchall()
        return {'tenant_id': tenant_id, 'ordering': 'fifo-per-tenant-key',
                'statuses': [dict(row) for row in rows]}

    def claim(self, *, tenant_id: str, worker_id: str, limit: int = 50,
              lease_seconds: int = 30) -> list[dict]:
        UUID(tenant_id)
        if (not 1 <= len(worker_id) <= 150 or type(limit) is not int or not 1 <= limit <= 100
                or type(lease_seconds) is not int or not 1 <= lease_seconds <= 300):
            raise ValueError('Invalid message lease')
        token = str(uuid4())
        with self.db.transaction():
            self.db.execute(
                """UPDATE event_outbox SET status='dead',lease_owner=NULL,lease_token=NULL,
                   last_error='lease-expired-attempt-limit'
                   WHERE tenant_id=%s AND message_kind IS NOT NULL AND status='leased'
                   AND available_at<=clock_timestamp() AND cycle_attempts>=3""", (tenant_id,))
            rows = self.db.execute(
                """WITH due AS (
                   SELECT o.id FROM event_outbox o
                   WHERE o.tenant_id=%s AND o.message_kind IS NOT NULL
                     AND o.status IN ('pending','leased') AND o.available_at<=clock_timestamp()
                     AND o.cycle_attempts<3 AND NOT EXISTS (
                       SELECT 1 FROM event_outbox earlier WHERE earlier.tenant_id=o.tenant_id
                       AND earlier.ordering_key=o.ordering_key AND earlier.sequence<o.sequence
                       AND earlier.status IN ('pending','leased'))
                   ORDER BY o.sequence FOR UPDATE OF o SKIP LOCKED LIMIT %s)
                   UPDATE event_outbox o SET status='leased',lease_owner=%s,lease_token=%s,
                     available_at=clock_timestamp()+(%s*interval '1 second'),
                     attempts=attempts+1,cycle_attempts=cycle_attempts+1
                   FROM due WHERE o.id=due.id RETURNING o.*""",
                (tenant_id, limit, worker_id, token, lease_seconds)).fetchall()
        return sorted([dict(row) for row in rows], key=lambda row: row['sequence'])

    def fail(self, *, tenant_id: str, message_id: str, lease_token: str,
             category: str = 'handler-failed') -> bool:
        for identifier in (tenant_id, message_id, lease_token):
            UUID(identifier)
        if category not in {'handler-failed', 'unregistered-handler', 'invalid-envelope'}:
            raise ValueError('Unsafe message error category')
        row = self.db.execute(
            """UPDATE event_outbox SET status=CASE WHEN cycle_attempts>=3 THEN 'dead' ELSE 'pending' END,
               available_at=clock_timestamp()+(LEAST(power(2,cycle_attempts),60)*interval '1 second'),
               lease_owner=NULL,lease_token=NULL,last_error=%s
               WHERE tenant_id=%s AND id=%s AND status='leased' AND lease_token=%s
                 AND available_at>clock_timestamp() RETURNING id""",
            (category, tenant_id, message_id, lease_token)).fetchone()
        return row is not None

    def dispatch(self, *, tenant_id: str, message_id: str, lease_token: str,
                 consumer: str, handler: Callable[[DatabaseConnection, dict], dict]) -> bool:
        for identifier in (tenant_id, message_id, lease_token):
            UUID(identifier)
        if not 1 <= len(consumer) <= 150:
            raise ValueError('Invalid consumer identity')
        with self.db.transaction():
            row = self.db.execute(
                """SELECT * FROM event_outbox WHERE tenant_id=%s AND id=%s AND status='leased'
                   AND lease_token=%s AND available_at>clock_timestamp() FOR UPDATE""",
                (tenant_id, message_id, lease_token)).fetchone()
            if row is None:
                return False
            envelope = MessageEnvelope(row['message_kind'], row['name'], str(row['tenant_id']),
                str(row['actor_id']), row['correlation_id'], row['operation_key'],
                row['ordering_key'], json.dumps(row['payload'], sort_keys=True))
            if envelope.digest() != row['body_sha256']:
                raise ValueError('Message digest mismatch')
            inserted = self.db.execute(
                """INSERT INTO event_inbox(consumer,event_id) VALUES(%s,%s)
                   ON CONFLICT DO NOTHING RETURNING event_id""", (consumer, message_id)).fetchone()
            if inserted:
                result = handler(self.db, dict(row))
                body = json.dumps(result, allow_nan=False)
                if not isinstance(result, dict) or len(body.encode()) > 8192:
                    raise ValueError('Invalid bounded message receipt')
                self.db.execute(
                    """INSERT INTO ago_message_receipts(tenant_id,event_id,consumer,result)
                       VALUES(%s,%s,%s,%s::jsonb)""", (tenant_id, message_id, consumer, body))
            acknowledged = self.db.execute(
                """UPDATE event_outbox SET status='delivered',lease_owner=NULL,lease_token=NULL,last_error=NULL
                   WHERE tenant_id=%s AND id=%s AND lease_token=%s AND available_at>clock_timestamp()
                   RETURNING id""", (tenant_id, message_id, lease_token)).fetchone()
            if acknowledged is None:
                raise PermissionError('Lease expired during dispatch; effects rolled back')
        return True

    def replay(self, *, actor: Principal, message_id: str, reason: str) -> bool:
        UUID(message_id)
        if not 1 <= len(reason.strip()) <= 500:
            raise ValueError('Replay rationale required')
        with self.db.transaction():
            controls = self.repositories.resolve(SecurityControls)
            if not controls.permitted(actor, 'messages:replay', actor.tenant_id):
                raise PermissionError('Replay permission required')
            human = self.db.execute(
                "SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND kind='human'",
                (actor.tenant_id, actor.subject)).fetchone()
            if not human:
                raise PermissionError('Human operator replay required')
            row = self.db.execute(
                """UPDATE event_outbox SET status='pending',cycle_attempts=0,replay_count=replay_count+1,
                   available_at=clock_timestamp(),lease_owner=NULL,lease_token=NULL,last_error=NULL
                   WHERE tenant_id=%s AND id=%s AND message_kind IS NOT NULL AND status='dead'
                   RETURNING id""", (actor.tenant_id, message_id)).fetchone()
            if row:
                controls.audit('message.replay', 'accepted', tenant_id=actor.tenant_id,
                               actor_id=actor.subject, metadata={'message_id': message_id, 'reason': reason.strip()})
        return row is not None
