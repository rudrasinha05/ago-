"""Envelope security and real transactional delivery, fencing and replay evidence."""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

import pytest
import test_m6_http_integration as m6

from ago.message_contracts import MessageEnvelope
from ago.message_store import MessageStore
from ago.bootstrap import bootstrap
from ago.security import Principal

case = m6.case
post = m6.post


@pytest.mark.parametrize('kind', ['command', 'event', 'query', 'notification', 'approval'])
def test_five_envelopes(kind):
    payload = {'request_id': str(uuid4()), 'status': 'requested'} if kind == 'approval' else {'reference': 'safe'}
    envelope = MessageEnvelope(kind, 'test.message', str(uuid4()), str(uuid4()),
                               str(uuid4()), 'once', 'stream', json.dumps(payload))
    assert len(envelope.digest()) == 64


@pytest.mark.parametrize('payload', [{'nested': {'approved': True}}, {'access_token': 'secret'},
                                    {'number': float('nan')}, ['invalid'], {'text': 'x' * 8193}])
def test_untrusted_payload_rejected(payload):
    with pytest.raises(ValueError):
        MessageEnvelope('event', 'test.message', str(uuid4()), str(uuid4()), str(uuid4()),
                        'once', 'stream', json.dumps(payload))


def test_http_idempotency_auth_and_safe_observability(case):
    client, headers, info = case
    url = '/v1/knowledge/messages'
    body = {'kind': 'event', 'name': 'example.created', 'payload': {'reference': 'private-body'},
            'operation_key': 'same'}
    assert client.post(url, json=body).status_code == 401
    post(client, url, headers['reviewer1'], body, expected=403)
    first = post(client, url, headers['founder'], body)
    assert post(client, url, headers['founder'], body) == {'id': first['id'], 'duplicate': True}
    post(client, url, headers['founder'], body | {'payload': {'different': 1}}, expected=400)
    post(client, url, headers['founder'], body | {'tenant_id': str(uuid4())}, expected=422)
    inspection = client.get(url, headers=headers['founder'])
    assert inspection.status_code == 200 and 'private-body' not in inspection.text
    assert inspection.json()['metrics']['statuses'][0]['count'] == 1


def test_ordering_crash_fencing_atomic_effect_and_poison_replay(case):
    _, _, info = case
    db = info['db']
    actor = Principal(info['founder'], info['tenant'], ('founder',))
    store = MessageStore(db)
    identifiers = [store.publish(actor=actor, kind='event', name='example.created',
                  payload={'n': n}, operation_key=str(n))['id'] for n in range(3)]
    rows = store.claim(tenant_id=info['tenant'], worker_id='worker-a')
    assert [str(row['id']) for row in rows] == identifiers[:1]
    assert store.claim(tenant_id=info['tenant'], worker_id='worker-b') == []
    old_token = str(rows[0]['lease_token'])
    db.execute("UPDATE event_outbox SET available_at=now()-interval '1 second' WHERE id=%s", (identifiers[0],))
    new = store.claim(tenant_id=info['tenant'], worker_id='worker-b')[0]
    assert str(new['lease_token']) != old_token
    assert not store.dispatch(tenant_id=info['tenant'], message_id=identifiers[0],
                              lease_token=old_token, consumer='test', handler=lambda *_: {})
    def broken(connection, row):
        connection.execute('CREATE TEMP TABLE rollback_effect(value integer) ON COMMIT DROP')
        raise RuntimeError('private exception')
    with pytest.raises(RuntimeError):
        store.dispatch(tenant_id=info['tenant'], message_id=identifiers[0],
                       lease_token=str(new['lease_token']), consumer='test', handler=broken)
    assert db.execute('SELECT 1 FROM event_inbox WHERE event_id=%s', (identifiers[0],)).fetchone() is None
    assert store.dispatch(tenant_id=info['tenant'], message_id=identifiers[0],
                          lease_token=str(new['lease_token']), consumer='test', handler=lambda *_: {'ok': True})
    assert store.claim(tenant_id=info['tenant'], worker_id='worker-b')[0]['id'] == __import__('uuid').UUID(identifiers[1])
    for attempt in range(3):
        if attempt:
            db.execute("UPDATE event_outbox SET available_at=now()-interval '1 second' WHERE id=%s", (identifiers[1],))
            row = store.claim(tenant_id=info['tenant'], worker_id='poison')[0]
        else:
            row = db.execute('SELECT * FROM event_outbox WHERE id=%s', (identifiers[1],)).fetchone()
        assert store.fail(tenant_id=info['tenant'], message_id=identifiers[1],
                          lease_token=str(row['lease_token']), category='unregistered-handler')
    with pytest.raises(PermissionError):
        store.replay(actor=Principal(info['founder'], str(uuid4()), ('founder',)),
                     message_id=identifiers[1], reason='wrong tenant')
    assert store.replay(actor=actor, message_id=identifiers[1], reason='Handler repaired')
    current = db.execute('SELECT * FROM event_outbox WHERE id=%s', (identifiers[1],)).fetchone()
    assert current['attempts'] == 3 and current['replay_count'] == 1 and current['cycle_attempts'] == 0
    with pytest.raises(Exception):
        with db.transaction():
            db.execute("UPDATE event_outbox SET payload='{}' WHERE id=%s", (identifiers[0],))


def test_approval_envelope_never_grants_decision_authority(case):
    client, headers, info = case
    body = {'kind': 'approval', 'name': 'approval.requested', 'operation_key': 'approval',
            'payload': {'request_id': str(uuid4()), 'status': 'requested'}}
    post(client, '/v1/knowledge/messages', headers['founder'], body, expected=403)
    body['payload']['approved'] = True
    post(client, '/v1/knowledge/messages', headers['founder'], body, expected=400)


def test_real_independent_connections_publish_once_and_claim_disjoint():
    dsn = os.getenv('AGO_TEST_POSTGRES_DSN')
    if not dsn:
        pytest.skip('Requires PostgreSQL independent connections')
    import psycopg
    from psycopg.rows import dict_row
    with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as db:
        tenant, founder = bootstrap(db, organization='Distributed workers',
                                   email='worker@example.test', password='worker-test-password-123')
        actor = Principal(founder, tenant, ('founder',))
        barrier = Barrier(2)
        def publish(number):
            with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
                barrier.wait(timeout=10)
                return MessageStore(connection).publish(actor=actor, kind='event', name='example.created',
                    payload={'safe': True}, operation_key='once', ordering_key='first')
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(publish, range(2)))
        assert results[0]['id'] == results[1]['id'] and sorted(r['duplicate'] for r in results) == [False, True]
        MessageStore(db).publish(actor=actor, kind='notification', name='example.created',
                                payload={}, operation_key='second', ordering_key='second')
        def claim(number):
            with psycopg.connect(dsn, autocommit=True, row_factory=dict_row) as connection:
                barrier.wait(timeout=10)
                return MessageStore(connection).claim(tenant_id=tenant, worker_id=f'worker-{number}', limit=1)
        with ThreadPoolExecutor(max_workers=2) as pool:
            claimed = list(pool.map(claim, range(2)))
        assert len(claimed[0]) == len(claimed[1]) == 1
        assert claimed[0][0]['id'] != claimed[1][0]['id']
