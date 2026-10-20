"""Real database regression for tenant isolation, retries, staffing and task timeline."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ago.main import create_app
from ago.api_company_chat import ChatInput, StaffingInput
from ago.company_chat import CompanyChat
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee

BASE = '/v1/organization/company'


def message(**extra):
    return {'channel': 'global', 'body': 'A concrete research project requirement',
            'operation_key': str(uuid4()), **extra}


def test_map_routes_require_authentication():
    with TestClient(create_app()) as client:
        for path in ('/chat', '/activity'):
            assert client.get(BASE+path).status_code == 401
        assert client.post(BASE+'/chat', json=message()).status_code == 401


def test_chat_inputs_reject_spoofed_author_and_unbounded_body():
    with pytest.raises(ValueError):
        ChatInput(**message(author_name='Founder'))
    with pytest.raises(ValueError):
        ChatInput(**message(body='x'*20001))
    with pytest.raises(ValueError):
        StaffingInput(department_id=str(uuid4()), name='Scientist', requirement='short',
                      operation_key=str(uuid4()))


def test_unknown_channel_rejected_before_query():
    class NoDatabase:
        def execute(self, *args):
            raise AssertionError('Unknown channel must not query a dynamic table')
    store = CompanyChat(NoDatabase())
    for value in ('private:123', 'employee:not-a-uuid', 'department:;DROP TABLE'):
        with pytest.raises(ValueError):
            store.channel(str(uuid4()), value)


def test_chat_pagination_replies_and_exact_retries(case):
    client, headers, _ = case
    f = headers['founder']
    payload = message()
    first = post(client, BASE+'/chat', f, payload)
    assert post(client, BASE+'/chat', f, payload)['id'] == first['id']
    post(client, BASE+'/chat', f, {**payload, 'body': 'Changed request'}, expected=400)
    second = post(client, BASE+'/chat', f, message(reply_to=first['id']))
    result = client.get(BASE+'/chat?limit=1', headers=f).json()
    assert result['items'][0]['id'] == second['id']
    assert result['items'][0]['reply_body'] == payload['body']
    older = client.get(BASE+'/chat?limit=1&before='+str(result['next_before']), headers=f).json()
    assert older['items'][0]['id'] == first['id']
    post(client, BASE+'/chat', f, message(reply_to=999999999), expected=400)
    post(client, BASE+'/chat', f, message(channel='employee:'+str(uuid4())), expected=400)
    post(client, BASE+'/chat', f, message(body='   '), expected=400)


def test_staffing_maps_manager_and_records_requirement_once(case):
    client, headers, _ = case
    f = headers['founder']
    dep = department(client, f)
    manager = employee(client, f, dep)
    payload = {'department_id':dep, 'manager_id':manager, 'name':'Experiment Scientist',
               'requirement':'Research project requires reproducible experiments', 'operation_key':str(uuid4())}
    created = post(client, BASE+'/staffing', f, payload)
    assert created['manager_id'] == manager
    assert post(client, BASE+'/staffing', f, payload)['id'] == created['id']
    post(client, BASE+'/staffing', f, {**payload,'operation_key':str(uuid4())}, expected=400)
    timeline = client.get(BASE+'/chat?channel=department:'+dep, headers=f).json()['items']
    assert len(timeline) == 1
    assert timeline[0]['kind'] == 'staffing'
    assert payload['requirement'] in timeline[0]['body']
    assert timeline[0]['employee_id'] == created['id']


def test_task_status_is_saved_without_browser_polling(case):
    client, headers, info = case
    f = headers['founder']
    dep = department(client, f)
    worker = employee(client, f, dep)
    task = post(client, '/v1/tasks', f, {'assignee_id':worker,'action':'internal:brief'})
    timeline = client.get(BASE+'/chat', headers=f).json()['items']
    assert any(m['task_id']==task['id'] and m['kind']=='status' for m in timeline)
    assert client.get(BASE+'/activity', headers=f).json()[0]['status']=='proposed'
    # A different tenant's record is neither readable nor replyable.
    from ago.bootstrap import bootstrap
    tenant, _ = bootstrap(info['db'], organization='Other company', email='other@example.test',
                          password='other-test-password-123')
    other = info['login']('other@example.test','other-test-password-123',tenant)
    assert client.get(BASE+'/chat',headers=other).json()['items']==[]
    post(client,BASE+'/chat',other,message(reply_to=timeline[0]['id']),expected=400)
    assert client.get(BASE+'/chat?channel=department:'+dep,headers=other).status_code==400
