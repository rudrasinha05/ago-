"""P0 Global Chat accountability: real PostgreSQL and signed-session regressions.

System receipts are not AI acknowledgements; only real signed human replies or
existing governed task evidence can progress the order ledger.
"""
from uuid import uuid4

from ago.security_controls import SecurityControls
from ago.security import Principal
from ago.company_chat import CompanyChat
from ago.model_handlers import respond_company_chat
from test_m7_http_postgres import case as case, post
from test_enterprise_http_21_27 import department

BASE = '/v1/organization/company'


def make_staff(client, founder):
    dep = department(client, founder)
    ceo = post(client, '/v1/organization/employees', founder, {
        'department_id':dep,'name':'Company Executive','kind':'ai',
    })['id']
    worker = post(client, '/v1/organization/employees', founder, {
        'department_id':dep,'name':'Implementation Engineer','kind':'ai',
        'manager_id':ceo,
    })['id']
    post(client, BASE+'/board/appoint', founder, {
        'seat':'Strategy & Vision','employee_id':ceo,
    })
    return ceo,worker


def send(client, headers, body, **extra):
    return post(client, BASE+'/chat', headers, {
        'channel':'global','body':body,'operation_key':str(uuid4()),**extra,
    })


def test_founder_untagged_message_has_immediate_ceo_owned_pending_receipt(case):
    client, headers, info = case
    founder = headers['founder']
    ceo, worker = make_staff(client,founder)
    message = send(client, founder, 'How is AdmissionFlow progressing?')
    order = message['order']
    assert order['accountable_ceo_id'] == ceo
    assert order['state'] == 'awaiting_ack'
    assert order['intent'] == 'message'
    assert order['founder_order'] is True
    assert len(order['work_items']) == 1
    assert order['work_items'][0]['assignee_id'] == ceo
    assert order['work_items'][0]['status'] == 'awaiting_ack'
    assert order['verified_acknowledgements'] == 0
    assert order['system_receipt_only'] is True
    receipt = info['db'].execute("""
        SELECT author_id,author_name,reply_to,body FROM ago_company_chat
        WHERE tenant_id=%s AND id=%s
    """,(info['tenant'],order['receipt_message_id'])).fetchone()
    assert receipt['author_id'] is None
    assert receipt['author_name'] == 'AGO system · order intake'
    assert receipt['reply_to'] == message['id']
    assert 'PENDING' in receipt['body']
    assert 'no AI reply' in receipt['body']
    feed = client.get(BASE+'/chat',headers=founder).json()['items']
    original = next(m for m in feed if m['id'] == message['id'])
    assert original['order']['work_items'][0]['assignee_id'] == ceo
    assert original['order']['system_receipt_only'] is True
    assert info['db'].execute("""
        SELECT count(*) AS n FROM ago_governed_tasks WHERE tenant_id=%s
    """,(info['tenant'],)).fetchone()['n'] == 0


def test_explicit_tags_are_deduplicated_and_ceo_owns_every_order(case):
    client,headers,info=case
    founder=headers['founder']
    ceo,worker=make_staff(client,founder)
    payload={
        'channel':'global', 'body':'@{'+worker+'} please implement approved module',
        'intent':'order','mentions':[worker],
        'operation_key':str(uuid4()),
    }
    msg=post(client,BASE+'/chat',founder,payload)
    assert msg['order']['intent']=='order'
    assert msg['order']['mention_ids']==[worker]
    assert {x['assignee_id'] for x in msg['order']['work_items']}=={ceo,worker}
    assert all(x['status']=='awaiting_ack' for x in msg['order']['work_items'])
    assert post(client,BASE+'/chat',founder,payload)['id']==msg['id']
    count=info['db'].execute("""
        SELECT count(*) AS n FROM ago_chat_work_items
        WHERE tenant_id=%s AND message_id=%s
    """,(info['tenant'],msg['id'])).fetchone()['n']
    assert count==2
    post(client,BASE+'/chat',founder,{**payload,'intent':'message'},expected=400)
    post(client,BASE+'/chat',founder,
         {**payload,'mentions':[ceo],'operation_key':str(uuid4()),
          'body':'@{'+worker+'} please implement approved module'},
         expected=200)  # CEO and textual worker mention are both real recipients
    named=send(client,founder,'@Implementation Engineer please report actual status')
    assert named['order']['mention_ids']==[worker]


def test_unknown_employee_and_nonfounder_order_are_rejected_atomically(case):
    client,headers,info=case
    founder,reviewer=headers['founder'],headers['reviewer']
    ceo,_=make_staff(client,founder)
    before=info['db'].execute("""
        SELECT count(*) AS n FROM ago_company_chat
        WHERE tenant_id=%s AND author_id=%s
    """,(info['tenant'],info['founder_id'])).fetchone()['n']
    post(client,BASE+'/chat',founder,{
        'channel':'global','body':'@{'+str(uuid4())+'} send confidential result',
        'intent':'order','operation_key':str(uuid4())},expected=400)
    post(client,BASE+'/chat',founder,{
        'channel':'global','body':'Do internal work','mentions':[str(uuid4())],
        'operation_key':str(uuid4())},expected=400)
    post(client,BASE+'/chat',founder,{
        'channel':'global','body':'@NotAnEmployee please fix production',
        'operation_key':str(uuid4())},expected=400)
    assert info['db'].execute("""
        SELECT count(*) AS n FROM ago_company_chat
        WHERE tenant_id=%s AND author_id=%s
    """,(info['tenant'],info['founder_id'])).fetchone()['n']==before
    with info['db'].transaction():
        for permission in ('organization:read','task:read','messages:write',
                           'messages:read'):
            SecurityControls(info['db']).grant(info['tenant'],'reviewer',permission)
    post(client,BASE+'/chat',reviewer,{
        'channel':'global','body':'I am the CEO now', 'intent':'order',
        'operation_key':str(uuid4())},expected=403)
    post(client,BASE+'/chat',founder,{
        'channel':'employee:'+ceo,'body':'Orders must be global',
        'mentions':[ceo],'operation_key':str(uuid4())},expected=400)


def test_no_ai_ceo_yields_truthful_blocked_system_receipt(case):
    client,headers,info=case
    founder=headers['founder']
    msg=send(client,founder,'Build the next module')
    order=msg['order']
    assert order['state']=='blocked_no_ceo'
    assert order['accountable_ceo_id'] is None
    assert order['work_items']==[]
    receipt=info['db'].execute("""
        SELECT author_id,body FROM ago_company_chat
        WHERE tenant_id=%s AND id=%s
    """,(info['tenant'],order['receipt_message_id'])).fetchone()
    assert receipt['author_id'] is None
    assert 'BLOCKED' in receipt['body']
    assert 'No appointed AI CEO' in receipt['body']


def test_attached_task_must_be_existing_governed_work_for_actual_assignee(case):
    client,headers,info=case
    founder=headers['founder']
    ceo,worker=make_staff(client,founder)
    msg=send(client,founder,'@Implementation Engineer implement one verified feature',
             intent='order')
    assert {r['assignee_id'] for r in msg['order']['work_items']}=={ceo,worker}
    task=post(client,'/v1/tasks',founder,{'assignee_id':worker,'action':'internal:brief'})
    payload={'employee_id':worker,'task_id':task['id']}
    link=post(client,BASE+'/chat/orders/'+str(msg['id'])+'/link-task',founder,payload)
    assert link['verified_task_link'] is True
    assert link['task_status']=='proposed'
    assert link['ai_acknowledged'] is False
    assert link['task_executed_by_chat'] is False
    assert post(client,BASE+'/chat/orders/'+str(msg['id'])+'/link-task',
                founder,payload)['verified_task_link'] is True
    post(client,BASE+'/chat/orders/'+str(msg['id'])+'/link-task',founder,
         {'employee_id':ceo,'task_id':task['id']},expected=403)
    post(client,BASE+'/chat/orders/'+str(uuid4())+'/link-task',founder,
         payload,expected=422)  # path requires an integer message id
    current=client.get(BASE+'/chat',headers=founder).json()['items']
    linked=next(x for x in current if x['id']==msg['id'])
    assigned=next(x for x in linked['order']['work_items'] if x['assignee_id']==worker)
    assert assigned['linked_task_id']==task['id']
    assert assigned['status']=='task_linked'



def test_founder_sees_durable_ceo_order_inbox_and_reviewer_cannot(case):
    client,headers,info=case
    founder,reviewer=headers['founder'],headers['reviewer']
    ceo,worker=make_staff(client,founder)
    one=send(client,founder,'Founder order: verify admission role permissions',
             mentions=[worker],intent='order')
    two=send(client,founder,'CEO must respond to this question too.')
    inbox=client.get(BASE+'/chat/orders',headers=founder)
    assert inbox.status_code==200, inbox.text
    rows=inbox.json()
    assert [r['message_id'] for r in rows[:2]]==[two['id'],one['id']]
    assert rows[0]['accountable_ceo_id']==ceo
    assert rows[0]['awaiting_ack_count']==1
    assert rows[1]['awaiting_ack_count']==2
    assert {x['assignee_id'] for x in rows[1]['work_items']}=={ceo,worker}
    assert all(x['linked_task_id'] is None for x in rows[1]['work_items'])
    assert client.get(BASE+'/chat/orders',headers=reviewer).status_code==403
    assert client.get(BASE+'/chat/orders?limit=101',headers=founder).status_code==422


def test_signed_human_addressee_ack_only_self_not_fake_ai(case):
    client,headers,info=case
    founder,reviewer=headers['founder'],headers['reviewer']
    ceo,_=make_staff(client,founder)
    with info['db'].transaction():
        for permission in ('organization:read','task:read','messages:write',
                           'messages:read'):
            SecurityControls(info['db']).grant(info['tenant'],'reviewer',permission)
    reviewer_id=info['reviewer_id']
    msg=send(client,founder,'Please acknowledge the review request',
             mentions=[reviewer_id])
    assert {x['assignee_id'] for x in msg['order']['work_items']}=={ceo,reviewer_id}
    response=send(client,reviewer,'Received; will review approved evidence',
                  reply_to=msg['order']['receipt_message_id'])
    member=info['db'].execute("""
        SELECT status,ack_message_id FROM ago_chat_work_items
        WHERE tenant_id=%s AND message_id=%s AND assignee_id=%s
    """,(info['tenant'],msg['id'],reviewer_id)).fetchone()
    assert member['status']=='acknowledged'
    assert member['ack_message_id']==response['id']
    ceo_rec=info['db'].execute("""
        SELECT status,ack_message_id FROM ago_chat_work_items
        WHERE tenant_id=%s AND message_id=%s AND assignee_id=%s
    """,(info['tenant'],msg['id'],ceo)).fetchone()
    assert ceo_rec['status']=='awaiting_ack'
    assert ceo_rec['ack_message_id'] is None


def test_real_local_model_reply_is_evidence_backed_and_idempotent(case):
    client,headers,info=case
    founder=headers['founder']
    ceo,worker=make_staff(client,founder)
    msg=send(client,founder,'Please describe the next approved UI task',
             intent='order',mentions=[worker])
    actor=Principal(subject=info['founder_id'],tenant_id=info['tenant'],roles=('founder',))
    store=CompanyChat(info['db'])

    class LocalTestModel:
        calls=0
        def generate(self,prompt):
            self.calls+=1
            assert 'Company Executive' in prompt
            assert 'next approved UI task' in prompt
            return 'Received. I will review the approved UI scope and report blockers.'

    fake=LocalTestModel()
    result=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                                employee_id=ceo,provider=fake)
    assert result['status']=='responded'
    assert result['source']=='local_ollama_model'
    assert result['ai_acknowledged'] is True
    assert result['task_executed'] is False
    assert fake.calls==1
    duplicate=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                                   employee_id=ceo,provider=fake)
    assert duplicate['status']=='already_replied'
    assert fake.calls==1
    reply=info['db'].execute("""
        SELECT author_id,author_name,body,reply_to,employee_id
        FROM ago_company_chat WHERE tenant_id=%s AND id=%s
    """,(info['tenant'],result['ack_message_id'])).fetchone()
    assert reply['author_id'] is None
    assert reply['author_name']=='AGO local AI · Company Executive'
    assert reply['reply_to']==msg['id']
    assert str(reply['employee_id'])==ceo
    assert 'not task execution/QA evidence' in reply['body']
    inbox=client.get(BASE+'/chat/orders',headers=founder).json()
    order=next(x for x in inbox if x['message_id']==msg['id'])
    assert order['real_ai_replies']==1
    assert order['verified_acknowledgements']==1
    assert order['awaiting_ack_count']==1
    assert order['system_receipt_only'] is False
    assert len([x for x in order['work_items'] if x['status']=='acknowledged'])==1
    assert all(not x['release_verified'] for x in order['work_items'])


def test_failed_local_model_never_forges_ack_and_can_retry(case):
    client,headers,info=case
    founder=headers['founder']
    ceo,_=make_staff(client,founder)
    msg=send(client,founder,'CEO please verify whether the engineer is available')
    actor=Principal(subject=info['founder_id'],tenant_id=info['tenant'],roles=('founder',))
    store=CompanyChat(info['db'])

    class BrokenModel:
        def generate(self,prompt):
            raise TimeoutError('Local model did not respond')

    first=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                               employee_id=ceo,provider=BrokenModel())
    assert first['status']=='model_unavailable'
    assert first['ai_acknowledged'] is False
    assert first['reason'].startswith('Local model call failed')
    assert store.chat_order_inbox(actor)[0]['verified_acknowledgements']==0
    attempts=info['db'].execute("""
        SELECT response_attempts,response_claim_token,ack_message_id
        FROM ago_chat_work_items WHERE tenant_id=%s AND message_id=%s
          AND assignee_id=%s
    """,(info['tenant'],msg['id'],ceo)).fetchone()
    assert attempts['response_attempts']==1
    assert attempts['response_claim_token'] is None
    assert attempts['ack_message_id'] is None

    class RecoveredModel:
        def generate(self,prompt):
            return 'Acknowledged. I need verified task data before reporting progress.'

    restored=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                                  employee_id=ceo,provider=RecoveredModel())
    assert restored['status']=='responded'
    assert store.chat_order_inbox(actor)[0]['verified_acknowledgements']==1


def test_ai_reply_rejects_reviewer_and_unassigned_worker(case,monkeypatch):
    client,headers,info=case
    founder=headers['founder']
    ceo,worker=make_staff(client,founder)
    msg=send(client,founder,'CEO-only status update, no specialist tag')
    actor=Principal(subject=info['founder_id'],tenant_id=info['tenant'],roles=('founder',))
    reviewer=Principal(subject=info['reviewer_id'],tenant_id=info['tenant'],roles=('reviewer',))
    store=CompanyChat(info['db'])
    class FakeModel:
        def generate(self,prompt):
            return 'Received; pending approval.'

    from pytest import raises
    with raises(PermissionError):
        respond_company_chat(actor=reviewer,store=store,message_id=msg['id'],
                             employee_id=ceo,provider=FakeModel())
    with raises(ValueError):
        respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                             employee_id=worker,provider=FakeModel())
    monkeypatch.setenv('AGO_LLM_PROVIDER','ollama_local')
    monkeypatch.setenv('AGO_ENABLE_LOCAL_MODELS','false')
    disabled=post(client,BASE+'/chat/orders/'+str(msg['id'])+'/respond',founder,
                  {'employee_id':ceo})
    assert disabled['status']=='local_model_disabled'
    assert disabled['ai_acknowledged'] is False
    assert client.post(BASE+'/chat/orders/'+str(msg['id'])+'/respond',
                      json={'employee_id':ceo}).status_code==401


def test_real_governed_task_status_and_qa_are_not_conflated_with_ack(case):
    client,headers,info=case
    founder=headers['founder']
    ceo,worker=make_staff(client,founder)
    msg=send(client,founder,'@Implementation Engineer build approved internal module')
    task=post(client,'/v1/tasks',founder,
              {'action':'internal:brief','assignee_id':worker})
    post(client,BASE+'/chat/orders/'+str(msg['id'])+'/link-task',founder,
         {'employee_id':worker,'task_id':task['id']})
    item=next(x for x in client.get(BASE+'/chat/orders',headers=founder).json()[0]
              ['work_items'] if x['assignee_id']==worker)
    assert item['status']=='task_linked'
    assert item['evidence_state']=='task_linked'
    assert item['task_status']=='proposed'
    assert item['qa_verdict'] is None
    assert item['has_execution_evidence'] is False
    assert item['ack_message_id'] is None
    assert item['release_verified'] is False



def test_tagged_specialist_receives_only_verified_saved_ceo_model_context(case):
    client,headers,info=case
    ceo,worker=make_staff(client,headers['founder'])
    msg=send(client,headers['founder'],
             'Founder order: plan UI implementation with CEO handoff',
             intent='order',mentions=[worker])
    actor=Principal(subject=info['founder_id'],tenant_id=info['tenant'],roles=('founder',))
    store=CompanyChat(info['db'])

    class CeoModel:
        def generate(self,prompt):
            assert 'Previously recorded AI team replies' in prompt
            assert '[]' in prompt
            return 'CEO reviewed the scope. Engineering should draft a test plan.'

    first=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                               employee_id=ceo,provider=CeoModel())
    assert first['status']=='responded'

    class EngineerModel:
        def generate(self,prompt):
            assert 'CEO Chat Acceptance' not in prompt
            assert 'Company Executive' in prompt
            assert 'Engineering should draft a test plan' in prompt
            assert 'NOT task completion or approval evidence' in prompt
            return 'Understood CEO handoff. I will prepare a proposed test plan.'

    second=respond_company_chat(actor=actor,store=store,message_id=msg['id'],
                                employee_id=worker,provider=EngineerModel())
    assert second['status']=='responded'
    inbox=store.chat_order_inbox(actor)
    order=next(x for x in inbox if x['message_id']==msg['id'])
    assert order['real_ai_replies']==2
    assert order['awaiting_ack_count']==0
    assert order['verified_acknowledgements']==2
    assert all(x['evidence_state']=='acknowledged' for x in order['work_items'])
    assert all(not x['has_execution_evidence'] for x in order['work_items'])
