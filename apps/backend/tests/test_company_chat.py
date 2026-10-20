"""Real database regression for tenant isolation, retries, staffing and task timeline."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ago.main import create_app
from ago.api_company_chat import ChatInput, StaffingInput, ReportInput, RoleProfileInput
from ago.company_chat import CompanyChat
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department, employee

BASE = '/v1/organization/company'


def message(**extra):
    return {'channel': 'global', 'body': 'A concrete research project requirement',
            'operation_key': str(uuid4()), **extra}


def test_map_routes_require_authentication():
    with TestClient(create_app()) as client:
        for path in ('/chat', '/activity', '/notifications'):
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
    notifications = client.get(BASE+'/notifications', headers=f).json()
    assert notifications['by_employee'][worker] >= 1
    assert any(event['task_id'] == task['id'] for event in notifications['recent'])
    assert notifications['event_type'] == 'committed_work_event'
    # A different tenant's record is neither readable nor replyable.
    from ago.bootstrap import bootstrap
    tenant, _ = bootstrap(info['db'], organization='Other company', email='other@example.test',
                          password='other-test-password-123')
    other = info['login']('other@example.test','other-test-password-123',tenant)
    assert client.get(BASE+'/chat',headers=other).json()['items']==[]
    assert client.get(BASE+'/notifications',headers=other).json()['recent']==[]
    post(client,BASE+'/chat',other,message(reply_to=timeline[0]['id']),expected=400)
    assert client.get(BASE+'/chat?channel=department:'+dep,headers=other).status_code==400


def test_notification_counters_are_persistent_and_tenant_scoped(case):
    client, headers, info = case
    founder = headers['founder']
    dep = department(client, founder)
    worker = employee(client, founder, dep)
    initial = client.get(BASE+'/notifications', headers=founder).json()
    assert initial['by_employee'][worker] == 0
    # Simulate two transactionally committed task-status audit entries.
    task = post(client, '/v1/tasks', founder, {'assignee_id': worker, 'action': 'internal:brief'})
    after_task = client.get(BASE+'/notifications', headers=founder).json()
    assert after_task['by_employee'][worker] == 1
    with info['db'].transaction():
        info['db'].execute("""
            INSERT INTO ago_company_chat
              (tenant_id, channel, author_name, body, kind, employee_id, task_id)
            VALUES (%s, %s, %s, %s, 'status', %s, %s)
        """, (info['tenant'], 'employee:'+worker, 'Work audit', 'Module checkpoint recorded', worker, task['id']))
    after_report = client.get(BASE+'/notifications', headers=founder).json()
    assert after_report['by_employee'][worker] == 2
    assert after_report['recent'][0]['body'] == 'Module checkpoint recorded'

def test_founder_approves_real_board_seat_and_role_profile(case):
    client, headers, _ = case
    founder, reviewer = headers["founder"], headers["reviewer"]
    dep = department(client, founder)
    worker = employee(client, founder, dep)
    role = {"role_title":"Engineering Lead", "core_responsibilities":"Review architecture and delivery",
            "extra_responsibilities":"Maintain source documents and test results"}
    update = client.put(BASE+"/employees/"+worker+"/role",json=role,headers=founder)
    assert update.status_code == 200, update.text
    assert update.json()["role_title"] == "Engineering Lead"
    denied = client.put(BASE+"/employees/"+worker+"/role",json=role,headers=reviewer)
    assert denied.status_code == 403,denied.text
    appointment = {"seat":"Technology Oversight","employee_id":worker}
    created = post(client, BASE+"/board/appoint", founder, appointment)
    assert created["authority_granted"] is False
    assert post(client,BASE+"/board/appoint",founder,appointment)["unchanged"] is True
    post(client,BASE+"/board/appoint",reviewer,appointment,expected=403)
    result = client.get(BASE+"/governance",headers=founder).json()
    assert any(e["id"]==worker and e["extra_responsibilities"]==role["extra_responsibilities"]
               for e in result["employees"])
    assert any(s["seat"]=="Technology Oversight" and s["employee_id"]==worker
               for s in result["board"])
    assert result["board_grants_authority"] is False


def test_reports_go_only_to_immediate_superior_and_increment_event_badge(case):
    from ago.security_controls import SecurityControls
    client,headers,info=case
    founder,reviewer=headers["founder"],headers["reviewer"]
    with info["db"].transaction():
        # Existing independently provisioned reviewer is a real human employee.
        info["db"].execute("""
            UPDATE ago_employees SET manager_id=%s WHERE tenant_id=%s AND id=%s
        """,(info["founder_id"],info["tenant"],info["reviewer_id"]))
        SecurityControls(info["db"]).grant(info["tenant"],"reviewer","messages:write")
        SecurityControls(info["db"]).grant(info["tenant"],"reviewer","messages:read")
    payload={"kind":"module_complete","body":"Module complete; tests and docs attached to reviewed GitHub work",
             "operation_key":str(uuid4())}
    first=post(client,BASE+"/reports",reviewer,payload)
    assert str(first["recipient_id"])==info["founder_id"]
    assert post(client,BASE+"/reports",reviewer,payload)["id"]==first["id"]
    post(client,BASE+"/reports",reviewer,{**payload,"body":"Changed"},expected=400)
    reports=client.get(BASE+"/reports",headers=founder).json()
    assert any(r["id"]==first["id"] and r["kind"]=="module_complete" for r in reports)
    events=client.get(BASE+"/notifications",headers=founder).json()
    assert events["by_employee"][info["reviewer_id"]]==1
    assert events["recent"][0]["kind"]=="report"
    # Shared activity does not disclose the private report body.
    global_chat=client.get(BASE+"/chat",headers=founder).json()["items"]
    assert any(m["kind"]=="report" for m in global_chat)
    assert all(payload["body"] not in m["body"] for m in global_chat)
    # Manager is a destination, not an arbitrary actor-supplied recipient.
    with pytest.raises(ValueError):
        ReportInput(**{**payload,"recipient_id":str(uuid4())})
    # Founder cannot report to self; root user must have an actual superior.
    post(client,BASE+"/reports",founder,{**payload,"operation_key":str(uuid4())},expected=403)
