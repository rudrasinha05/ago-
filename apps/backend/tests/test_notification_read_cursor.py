"""Durable notification acknowledgements using actual signed PostgreSQL sessions."""
import pytest

from ago.api_company_chat import NotificationReadInput
from ago.bootstrap import bootstrap
from ago.company_chat import CompanyChat
from test_m7_http_postgres import case as case, post

BASE = '/v1/organization/company/notifications'


@pytest.fixture
def readers(case):
    from ago.security_controls import SecurityControls
    _, _, info = case
    for permission in ('organization:read', 'task:read'):
        SecurityControls(info['db']).grant(info['tenant'], 'reviewer', permission)
    return case


def event(info, *, employee=None, kind='status'):
    return info['db'].execute('''
        INSERT INTO ago_company_chat(tenant_id,channel,author_name,body,kind,employee_id)
        VALUES (%s,'global','Recorded work','Checkpoint',%s,%s) RETURNING id
    ''', (info['tenant'], kind, employee or info['reviewer_id'])).fetchone()['id']


@pytest.mark.parametrize('value', [-1, True, 1.5, '1', 9007199254740992])
def test_read_input_rejects_invalid_cursor(value):
    with pytest.raises(ValueError):
        NotificationReadInput(through_id=value)


def test_read_input_cannot_override_reader():
    with pytest.raises(ValueError):
        NotificationReadInput(through_id=0, reader_id='another-user')


def test_read_cursor_persists_and_does_not_acknowledge_new_events(readers):
    client, headers, info = readers
    first = event(info)
    second = event(info)
    initial = client.get(BASE, headers=headers['founder']).json()
    assert initial['read_through_id'] == 0
    assert initial['unread_count'] == 2
    result = post(client, BASE+'/read', headers['founder'], {'through_id': second})
    assert result['read_through_id'] == second
    assert result['unread_count'] == 0
    # A stale tab or retry cannot move the cursor backwards.
    for through in (second, first, 0):
        assert post(client, BASE+'/read', headers['founder'], {'through_id': through})['read_through_id'] == second
    latest = event(info)
    # Fresh repository instance reads persisted state, independent of UI/poll cursor.
    fresh = CompanyChat(info['db']).notifications(info['tenant'], info['founder_id'], after_id=latest)
    assert fresh['recent'] == []
    assert fresh['read_through_id'] == second
    assert fresh['unread_count'] == 1
    assert fresh['unread_by_employee'] == {info['reviewer_id']: 1}


def test_counts_include_events_outside_the_page_and_reader_state_is_independent(readers):
    client, headers, info = readers
    ids = [event(info) for _ in range(105)]
    initial = client.get(BASE, headers=headers['founder']).json()
    assert len(initial['recent']) == 100
    assert initial['unread_count'] == 105
    post(client, BASE+'/read', headers['founder'], {'through_id': ids[-1]})
    own = client.get(BASE, headers=headers['reviewer'])
    assert own.status_code == 200, own.text
    assert own.json()['unread_count'] == 105
    post(client, BASE+'/read', headers['reviewer'], {'through_id': ids[0]})
    assert client.get(BASE, headers=headers['reviewer']).json()['unread_count'] == 104
    assert client.get(BASE, headers=headers['founder']).json()['unread_count'] == 0


def test_hidden_foreign_non_event_and_future_ids_cannot_advance_cursor(readers):
    client, headers, info = readers
    hidden = event(info, employee=info['founder_id'])
    ordinary = event(info, kind='message')
    own = event(info)
    tenant, _ = bootstrap(info['db'], organization='Other notifications',
                          email='other-read@example.test', password='other-notify-password-123')
    other = info['login']('other-read@example.test', 'other-notify-password-123', tenant)
    post(client, BASE+'/read', other, {'through_id': own}, expected=400)
    for through in (hidden, ordinary, own + 100000):
        post(client, BASE+'/read', headers['reviewer'], {'through_id': through}, expected=400)
    assert client.get(BASE, headers=headers['reviewer']).json()['read_through_id'] == 0
    assert client.get(BASE, headers=other).json()['unread_count'] == 0


def test_read_requires_auth_and_live_active_reader(readers):
    client, headers, info = readers
    assert client.post(BASE+'/read', json={'through_id': 0}).status_code == 401
    first = event(info)
    info['db'].execute('UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s',
                       (info['tenant'], info['reviewer_id']))
    with pytest.raises(PermissionError):
        CompanyChat(info['db']).mark_notifications_read(info['tenant'], info['reviewer_id'], first)
    assert not info['db'].execute('SELECT 1 FROM ago_notification_read_cursors WHERE tenant_id=%s',
                                  (info['tenant'],)).fetchone()
