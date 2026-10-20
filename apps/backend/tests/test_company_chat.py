"""Real database regression for tenant isolation, retries, staffing and task timeline."""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from ago.main import create_app
from ago.api_company_chat import ChatInput, StaffingInput, ReportInput
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
    profile = client.get(BASE+'/governance',headers=f).json()['employees']
    assert any(e['id']==created['id'] and e['role_title']==payload['name']
               and e['core_responsibilities']==payload['requirement'] for e in profile)



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


def test_completed_ai_run_reports_to_actual_manager_and_creates_popup(case):
    client, headers, info = case
    f = headers["founder"]
    dep = department(client,f)
    manager = employee(client,f,dep)
    agent = post(client,"/v1/organization/employees",f,
                 {"department_id":dep,"name":"Report Agent","kind":"ai",
                  "manager_id":manager})["id"]
    task = post(client,"/v1/tasks",f,{"assignee_id":agent,"action":"internal:brief"})
    run_id = str(uuid4())
    with info["db"].transaction():
        info["db"].execute("""
            INSERT INTO ago_agent_runs(id,tenant_id,task_id,agent_id,executor_id,status)
            VALUES(%s,%s,%s,%s,%s,'running')
        """,(run_id,info["tenant"],task["id"],agent,info["founder_id"]))
        info["db"].execute("""
            UPDATE ago_agent_runs SET status='completed',finished_at=now()
            WHERE tenant_id=%s AND id=%s
        """,(info["tenant"],run_id))
    event=info["db"].execute("""
        SELECT author_id,recipient_id,kind,operation_key FROM ago_company_reports
        WHERE tenant_id=%s AND task_id=%s
    """,(info["tenant"],task["id"])).fetchone()
    assert str(event["author_id"])==agent
    assert str(event["recipient_id"])==manager
    assert event["kind"]=="module_complete"
    assert str(event["operation_key"])==run_id
    feed=client.get(BASE+"/notifications",headers=f).json()
    assert feed["by_employee"][agent]>=2
    assert any(row["kind"]=="report" and row["employee_id"]==agent
               for row in feed["recent"])


def test_founder_one_prompt_creates_durable_draft_and_never_dispatches(case):
    client,headers,info=case
    founder,reviewer=headers['founder'],headers['reviewer']
    original='Build an admission enquiry management application with followups, roles, documentation, accessibility, security, QA and reviewed GitHub release.'
    payload={'brief':original,'operation_key':str(uuid4())}
    first=post(client,BASE+'/projects/start',founder,payload)
    assert first['automatic_execution'] is False
    assert first['plan_status']=='draft'
    assert first['approval_required'] is True
    assert [s['stage'] for s in first['stages']]==[
        'discovery','architecture','implementation','quality','release']
    assert len([s for s in first['stages'] if s['staffing_required']])>=4
    assert all(not s['plan_step_id'] for s in first['stages'])
    replay=post(client,BASE+'/projects/start',founder,payload)
    assert replay['reused'] is True
    assert replay['goal_id']==first['goal_id'] and replay['plan_id']==first['plan_id']
    post(client,BASE+'/projects/start',founder,
         {**payload,'brief':'Another unrelated valid startup project prompt'},expected=400)
    post(client,BASE+'/projects/start',reviewer,
         {**payload,'operation_key':str(uuid4())},expected=403)
    rows=client.get(BASE+'/projects',headers=founder).json()
    assert any(str(r['id'])==first['id'] for r in rows)
    assert not info['db'].execute("""
        SELECT 1 FROM ago_governed_tasks WHERE tenant_id=%s
    """,(info['tenant'],)).fetchone()
    from ago.bootstrap import bootstrap
    other,_=bootstrap(info['db'],organization='Separate founder tenant',
                      email='isolated@sample.test',password='isolated-password-123')
    remote=info['login']('isolated@sample.test','isolated-password-123',other)
    assert client.get(BASE+'/projects',headers=remote).json()==[]


def test_founder_intake_seeds_only_allowlisted_internal_brief_when_ai_staffed(case):
    client,headers,info=case
    founder=headers['founder']
    dep=department(client,founder)
    worker=employee(client,founder,dep)
    intake_payload={
        'brief':'Design a production-ready resource scheduling platform with source control, tests and documented user journeys.',
        'operation_key':str(uuid4()),
    }
    project=post(client,BASE+'/projects/start',founder,intake_payload)
    discovery=project['stages'][0]
    assert discovery['suggested_assignee_id']==worker
    assert discovery['plan_step_id'] is not None
    assert len([s for s in project['stages'] if s['plan_step_id']])==1
    rows=client.get('/v1/brain/plans/'+project['plan_id']+'/steps',headers=founder).json()
    assert len(rows)==1 and rows[0]['action']=='internal:brief'
    assert rows[0]['task_id'] is None
    assert not info['db'].execute("""
        SELECT 1 FROM ago_agent_runs WHERE tenant_id=%s
    """,(info['tenant'],)).fetchone()
    review=post(client,'/v1/brain/plans/'+project['plan_id']+'/submit',founder)
    assert review['status']=='pending_approval'
    replay=post(client,BASE+'/projects/start',founder,intake_payload)
    assert replay['reused'] is True
    assert replay['plan_status']=='pending_approval'
    approved=post(client,
       '/v1/governance/approvals/'+review['approval_id']+'/decision',
       headers['reviewer'],{'approve':True,'reason':'Approved bounded scope review'})
    assert approved['status']=='approved'
    post(client,'/v1/brain/plans/'+project['plan_id']+'/activate',founder)
    created=post(client,'/v1/brain/plans/'+project['plan_id']+'/materialize',founder)
    task_id=created['task_ids'][0]
    task_approval=post(client,'/v1/governance/approvals',founder,{'action':'internal:brief'})
    post(client,'/v1/tasks/'+task_id+'/approval',founder,
         {'approval_id':task_approval['request_id']})
    post(client,'/v1/governance/approvals/'+task_approval['request_id']+'/decision',
         headers['reviewer'],{'approve':True,'reason':'Independent task approval'})
    agent_run=post(client,'/v1/agents/tasks/'+task_id+'/run',founder)
    packet=agent_run['result']
    assert packet['kind']=='founder_scope_packet'
    assert packet['title']==project['title']
    assert intake_payload['brief'][:80] in packet['founder_brief_excerpt']
    assert packet['code_written'] is False
    assert packet['github_pushed'] is False
    assert packet['requires_human_qa'] is True




def test_company_approval_inbox_truthful_authority_and_cross_tenant(case):
    client,headers,info=case
    founder,reviewer=headers['founder'],headers['reviewer']
    original='Build a secure and accessible admissions portal with documented test coverage and an approval checkpoint'
    company=post(client,BASE+'/projects/start',founder,{'brief':original,'operation_key':str(uuid4())})
    # A registered research employee gives this plan an allowlisted draft step.
    dep=department(client,founder)
    analyst=employee(client,founder,dep)
    post(client,'/v1/brain/plans/'+company['plan_id']+'/steps',founder,
         {'action':'internal:brief','assignee_id':analyst})
    approval=post(client,'/v1/brain/plans/'+company['plan_id']+'/submit',founder)
    assert client.get(BASE+'/approvals').status_code==401
    response=client.get(BASE+'/approvals',headers=reviewer)
    assert response.status_code==200,response.text
    entry=next(x for x in response.json() if str(x['id'])==approval['approval_id'])
    assert entry['approval_type']=='plan_review'
    assert entry['plan_title']==company['title']
    assert entry['requester_name']=='Founder'
    assert str(entry['requester_id'])==info['founder_id']
    assert entry['reviewer_id'] is None
    assert entry['status']=='pending'
    assert entry['goal_brief_excerpt']==original
    assert 'Independent' in entry['review_routing']
    assert entry['task_id'] is None
    # No self-approval even when founder has granted decision permission.
    post(client,'/v1/governance/approvals/'+approval['approval_id']+'/decision',
         founder,{'approve':True,'reason':'Trying self-approval'},expected=403)
    post(client,'/v1/governance/approvals/'+approval['approval_id']+'/decision',
         reviewer,{'approve':False,'reason':'Acceptance criteria need revision'})
    updated=client.get(BASE+'/approvals',headers=founder).json()
    entry=next(x for x in updated if str(x['id'])==approval['approval_id'])
    assert entry['status']=='rejected' and entry['reason']=='Acceptance criteria need revision'
    assert str(entry['reviewer_id'])==info['reviewer_id']
    from ago.bootstrap import bootstrap
    other,_=bootstrap(info['db'],organization='Isolated approvals',
                      email='other-approvals@example.test',password='test-strong-password-123')
    other_auth=info['login']('other-approvals@example.test','test-strong-password-123',other)
    assert not any(str(a['id'])==approval['approval_id']
                   for a in client.get(BASE+'/approvals',headers=other_auth).json())
