"""Section30: real temporal governance, task admission and immutable provenance."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ago.enterprise_domains import (CALENDAR_DOMAINS, calendar_instant, calendar_policy_reasons,
                                    calendar_wall_time, validate_calendar_policy, validate_calendar_window)
from ago.calendar_store import CalendarStore
from ago.security import Principal
from ago.task_store import TaskStore
from test_enterprise_capacity_21 import _approved_task
from test_enterprise_durable_queue_21 import _enqueue
from test_enterprise_http_21_27 import department, employee
from test_m7_http_postgres import case as case, decide, post

BASE = '/v1/operations/calendar'


def proposal(client, founder, command, specification, **extra):
    revision = client.get(BASE+'/governance', headers=founder).json()['revision']
    data = dict(command=command, specification=specification, rationale='Bounded independent temporal review',
                operation_key=str(uuid4()), base_revision=revision)
    data.update(extra)
    return post(client, BASE+'/governance/proposals', founder, data), data


def apply(client, founder, reviewer, item):
    decide(client, reviewer, item['approval_id'])
    return post(client, BASE+'/governance/apply', founder, {'proposal_id': item['id']})


def window(kind='maintenance', start=None, end=None, **extra):
    now = datetime.now(timezone.utc)
    return dict(kind=kind, title='Reviewed '+kind, timezone='UTC',
                starts_at=(start or now-timedelta(minutes=1)).isoformat(),
                ends_at=(end or now+timedelta(hours=2)).isoformat(), **extra)


def event(client, founder, start, end, **extra):
    return post(client, BASE, founder, dict(title='Shared handoff', starts_at=start.isoformat(),
        ends_at=end.isoformat(), operation_key=str(uuid4()), **extra))['id']


@pytest.mark.parametrize('bad', [dict(timezone='Unknown/Zone'), dict(weekdays=[]), dict(weekdays=[True]),
    dict(weekdays=[{}]), dict(weekdays=[1,1]), dict(start='9:00'), dict(start='24:00'),
    dict(end='25:00'), dict(start='18:00',end='09:00'), dict(quiet_start='22:00'),
    dict(quiet_start='22:00',quiet_end='22:00'), dict(holidays=['2026-02-30']),
    dict(holidays=[{}]), dict(reviewer_ids=[{}]), dict(require_supervisor=True),
    dict(max_continuous_minutes=True), dict(rest_minutes=-1), dict(disable_approval=True),
    dict(scope_kind='employee'), dict(support_start='10:00')])
def test_policy_rejects_malformed_or_authority_changing_input(bad):
    with pytest.raises(ValueError):
        validate_calendar_policy(bad)


def test_iana_holidays_overnight_quiet_and_combined_duration():
    policy = validate_calendar_policy(dict(timezone='Asia/Kolkata', weekdays=[0,1,2,3,4],
        start='09:00', end='18:00', holidays=['2026-10-12'], quiet_start='22:00', quiet_end='07:00'))
    monday = datetime(2026,10,12,5,0,tzinfo=timezone.utc)
    assert calendar_policy_reasons(policy, monday, 1) == ['holiday']
    assert 'non_working_day' in calendar_policy_reasons(policy, monday-timedelta(days=1), 1)
    assert 'outside_working_hours' in calendar_policy_reasons(policy, monday+timedelta(hours=8), 1)
    overnight = validate_calendar_policy(dict(quiet_start='22:00', quiet_end='07:00'))
    assert calendar_policy_reasons(overnight, datetime(2026,10,12,23,tzinfo=timezone.utc), 1) == ['quiet_hours']
    assert 'quiet_hours' in calendar_policy_reasons(overnight, datetime(2026,10,13,6,59,tzinfo=timezone.utc), 2)
    assert calendar_policy_reasons(overnight, datetime(2026,10,13,7,tzinfo=timezone.utc), 1) == []
    with pytest.raises(ValueError):
        calendar_instant('2026-10-12T10:00:00')


def test_dst_gaps_folds_and_explicit_offsets():
    with pytest.raises(ValueError, match='Nonexistent'):
        calendar_wall_time(datetime(2026,3,8,2,30),'America/New_York')
    with pytest.raises(ValueError, match='ambiguous'):
        calendar_wall_time(datetime(2026,11,1,1,30),'America/New_York')
    first = calendar_wall_time(datetime(2026,11,1,1,30),'America/New_York',-14400)
    second = calendar_wall_time(datetime(2026,11,1,1,30),'America/New_York',-18000)
    assert second-first == timedelta(hours=1)
    with pytest.raises(ValueError, match='offset'):
        validate_calendar_window(dict(kind='learning',title='DST gap',timezone='America/New_York',
            starts_at='2026-03-08T02:30:00-05:00',ends_at='2026-03-08T03:30:00-04:00'))


def test_local_recurrence_preserves_wall_time_and_month_end():
    weekly = validate_calendar_window(dict(kind='weekly', title='Team planning', timezone='America/New_York',
        starts_at='2026-03-01T09:00:00-05:00', ends_at='2026-03-01T10:00:00-05:00',cadence='weekly',count=3))
    from zoneinfo import ZoneInfo
    assert [calendar_instant(x['starts_at']).astimezone(ZoneInfo('America/New_York')).hour for x in weekly['slots']] == [9,9,9]
    assert calendar_instant(weekly['slots'][1]['starts_at'])-calendar_instant(weekly['slots'][0]['starts_at']) == timedelta(days=7,hours=-1)
    monthly = validate_calendar_window(dict(kind='monthly',title='Monthly close',timezone='UTC',
        starts_at='2028-01-31T09:00:00+00:00',ends_at='2028-01-31T10:00:00+00:00',cadence='monthly',count=3))
    assert [x['starts_at'][:10] for x in monthly['slots']] == ['2028-01-31','2028-02-29','2028-03-31']


@pytest.mark.parametrize('kind', list(CALENDAR_DOMAINS))
def test_every_original_temporal_domain_has_bounded_owner_and_slots(kind):
    result = validate_calendar_window(window(kind=kind))
    assert result['owner'] == CALENDAR_DOMAINS[kind] and len(result['slots']) == 1


@pytest.mark.parametrize('bad', [dict(kind='grant_authority'), dict(cadence='daily'), dict(count=0),
    dict(count=True), dict(count=2), dict(cadence='annual',count=52), dict(depends_on=[{}]),
    dict(starts_at='2026-01-01'), dict(sprint_days=1), dict(scope_id=str(uuid4())),
    dict(disable_approval=True)])
def test_window_rejects_unknown_authority_recurrence_and_scope(bad):
    with pytest.raises(ValueError):
        validate_calendar_window({**window(), **bad})


def test_exact_independent_review_stale_retry_revocation_and_immutability(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    assert client.get(BASE+'/governance').status_code == 401
    assert client.get(BASE+'/governance',headers=f).json()['revision'] == 0
    item,data = proposal(client,f,'policy',dict(timezone='Asia/Kolkata'))
    assert post(client,BASE+'/governance/proposals',f,data)['id'] == item['id']
    post(client,BASE+'/governance/proposals',f,{**data,'rationale':'Changed retry'},expected=403)
    post(client,BASE+'/governance/proposals',r,data,expected=403)
    source = client.get(BASE+'/governance/approvals/'+item['approval_id'],headers=r).json()
    assert source['digest'] == item['digest'] and source['source']['input'] == data['specification']
    post(client,BASE+'/governance/apply',f,{'proposal_id':item['id']},expected=403)
    post(client,'/v1/governance/approvals/'+item['approval_id']+'/decision',f,
         {'approve':True,'reason':'Self review'},expected=403)
    stale,_ = proposal(client,f,'policy',dict(timezone='UTC'))
    result = apply(client,f,r,item)
    assert result['revision'] == 1
    assert post(client,BASE+'/governance/apply',f,{'proposal_id':item['id']})['idempotent']
    decide(client,r,stale['approval_id'])
    post(client,BASE+'/governance/apply',f,{'proposal_id':stale['id']},expected=403)
    current,_ = proposal(client,f,'policy',dict(timezone='UTC'))
    decide(client,r,current['approval_id'])
    info['db'].execute("DELETE FROM ago_role_permissions WHERE tenant_id=%s AND role='reviewer' AND permission='approval:decide'", (info['tenant'],))
    post(client,BASE+'/governance/apply',f,{'proposal_id':current['id']},expected=403)
    psycopg = pytest.importorskip('psycopg')
    for table in ('ago_calendar_proposals','ago_calendar_changes','ago_calendar_timing_audit'):
        with pytest.raises(psycopg.errors.RaiseException,match='append-only'):
            with info['db'].transaction():
                info['db'].execute('DELETE FROM '+table+' WHERE tenant_id=%s',(info['tenant'],))


@pytest.mark.parametrize('kind',['maintenance','incident','release_freeze','quiet'])
def test_approved_task_and_queue_block_then_reviewed_cancellation_restores_execution(case,kind):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    worker = employee(client,f,department(client,f))
    task = _approved_task(client,f,r,worker)
    item,_ = proposal(client,f,'window',window(kind))
    apply(client,f,r,item)
    _enqueue(client,f,task,90)
    leased = post(client,'/v1/operations/enterprise/work-queue/claim',f,{'lease_seconds':60})
    assert leased['queue_id'] is None
    for path in ('/v1/agents/tasks/'+task+'/run','/v1/tasks/'+task+'/start'):
        post(client,path,f,expected=403)
    actor = Principal(info['founder_id'],info['tenant'],('founder',))
    with pytest.raises(PermissionError,match='Calendar'):
        TaskStore(info['db']).authorize_and_start(task_id=task,principal=actor)
    state = client.get(BASE+'/governance',headers=f).json()
    assert any(x['kind']=='execution_denied' for x in state['signals'])
    assert info['db'].execute('SELECT count(*) AS n FROM ago_agent_runs WHERE tenant_id=%s',(info['tenant'],)).fetchone()['n'] == 0
    cancellation,_ = proposal(client,f,'window_cancel',dict(window_id=item['id']))
    apply(client,f,r,cancellation)
    assert post(client,'/v1/operations/enterprise/work-queue/claim',f,{'lease_seconds':60})['task_id'] == task
    post(client,'/v1/agents/tasks/'+task+'/run',f)
    post(client,'/v1/agents/tasks/'+task+'/run',f,expected=403)
    kinds = [x['kind'] for x in client.get(BASE+'/governance',headers=f).json()['signals']]
    assert 'execution_started' in kinds and 'execution_completed' in kinds


def test_holidays_quiet_supervisor_coverage_and_finite_next_window(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    worker = employee(client,f,department(client,f))
    now = datetime.now(timezone.utc)
    personal,_ = proposal(client,f,'policy',dict(scope_kind='employee',scope_id=info['reviewer_id'],holidays=[now.date().isoformat()]))
    apply(client,f,r,personal)
    team,_ = proposal(client,f,'policy',dict(scope_kind='employee',scope_id=worker,require_supervisor=True,reviewer_ids=[info['reviewer_id']]))
    apply(client,f,r,team)
    params = dict(employee_id=worker,at=now.isoformat(),duration_minutes=30,search_days=2)
    result = client.get(BASE+'/eligibility',headers=f,params=params)
    assert result.status_code == 200,result.text
    result = result.json()
    assert 'human_reviewer_unavailable' in result['reasons'] and result['next_eligible_at']
    assert not result['authority_changed'] and result['approval_still_required']
    params['employee_id'] = str(uuid4())
    assert client.get(BASE+'/eligibility',headers=f,params=params).status_code == 403
    post(client,BASE+'/governance/proposals',f,dict(command='policy',base_revision=2,operation_key=str(uuid4()),rationale='Invalid authority',
        specification=dict(scope_kind='employee',scope_id=worker,reviewer_ids=[worker])),expected=403)


def test_shared_event_conflicts_private_visibility_and_exact_cascaded_reschedule(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    now = datetime.now(timezone.utc)+timedelta(days=2)
    first = event(client,f,now,now+timedelta(hours=1),employee_ids=[info['reviewer_id']])
    second = event(client,f,now+timedelta(hours=2),now+timedelta(hours=3))
    post(client,BASE,f,dict(title='Overlapping',starts_at=now.isoformat(),ends_at=(now+timedelta(minutes=5)).isoformat(),operation_key=str(uuid4())),expected=403)
    linked,_ = proposal(client,f,'event_link',dict(event_id=second,depends_on=[first]))
    apply(client,f,r,linked)
    post(client,BASE+'/'+first+'/cancel',f,expected=403)
    candidate,data = proposal(client,f,'reschedule',dict(event_id=first,starts_at=(now+timedelta(days=1)).isoformat(),ends_at=(now+timedelta(days=1,hours=1)).isoformat()))
    assert len(candidate['specification']['moves']) == 2
    result = apply(client,f,r,candidate)
    assert len(result['result']['rescheduled']) == 2
    assert [x['replacement_id'] for x in result['result']['rescheduled']] == [x['replacement_id'] for x in candidate['specification']['moves']]
    assert post(client,BASE+'/governance/apply',f,{'proposal_id':candidate['id']})['idempotent']
    projection = client.get(BASE+'/governance',headers=f).json()
    assert first not in [x['event_id'] for x in projection['links']]
    private = event(client,f,now+timedelta(days=6),now+timedelta(days=6,hours=1),visibility='private')
    revision = projection['revision']
    post(client,BASE+'/governance/proposals',f,dict(command='event_link',specification=dict(event_id=private),rationale='Private source cannot enter shared review',operation_key=str(uuid4()),base_revision=revision),expected=403)
    # Normalization/source is re-read after independent review, not trusted forever.
    third = event(client,f,now+timedelta(days=8),now+timedelta(days=8,hours=1))
    stale,_ = proposal(client,f,'reschedule',dict(event_id=third,starts_at=(now+timedelta(days=9)).isoformat(),ends_at=(now+timedelta(days=9,hours=1)).isoformat()))
    decide(client,r,stale['approval_id'])
    post(client,BASE+'/'+third+'/cancel',f)
    post(client,BASE+'/governance/apply',f,{'proposal_id':stale['id']},expected=403)


def test_cycles_parent_dependencies_signals_and_twin_projection(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    now = datetime.now(timezone.utc)
    parent,_ = proposal(client,f,'window',window('annual',now-timedelta(days=1),now+timedelta(days=364)))
    apply(client,f,r,parent)
    child,_ = proposal(client,f,'window',window('monthly',now-timedelta(minutes=10),now+timedelta(hours=1),parent_id=parent['id']))
    apply(client,f,r,child)
    post(client,BASE+'/governance/proposals',f,dict(command='window_cancel',specification=dict(window_id=parent['id']),rationale='Parent still needed',operation_key=str(uuid4()),base_revision=2),expected=403)
    post(client,BASE+'/tick',f)
    count = info['db'].execute("SELECT count(*) AS n FROM ago_calendar_timing_audit WHERE tenant_id=%s AND kind='cycle_opened'",(info['tenant'],)).fetchone()['n']
    assert count == 2
    post(client,BASE+'/tick',f)
    assert info['db'].execute("SELECT count(*) AS n FROM ago_calendar_timing_audit WHERE tenant_id=%s AND kind='cycle_opened'",(info['tenant'],)).fetchone()['n'] == count
    twin = post(client,'/v1/operations/enterprise/twin/state',f,{'operation_key':str(uuid4())})
    assert twin['payload']['temporal_state']['revision'] == 2
    assert not twin['payload']['temporal_state']['authority_changed']
    assert CalendarStore(info['db']).temporal_snapshot(tenant_id=info['tenant'])['revision'] == 2


def test_task_event_deadline_applies_to_direct_start_and_queue(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    worker = employee(client,f,department(client,f))
    task = _approved_task(client,f,r,worker)
    now = datetime.now(timezone.utc)+timedelta(days=2)
    identifier = event(client,f,now,now+timedelta(hours=1))
    link,_ = proposal(client,f,'event_link',dict(event_id=identifier,task_id=task))
    apply(client,f,r,link)
    post(client,'/v1/agents/tasks/'+task+'/run',f,expected=403)
    result = client.get(BASE+'/eligibility',headers=f,params=dict(employee_id=worker,task_id=task,at=now.isoformat(),duration_minutes=30)).json()
    assert result['eligible']
    missed = client.get(BASE+'/eligibility',headers=f,params=dict(employee_id=worker,task_id=task,at=(now+timedelta(hours=2)).isoformat(),duration_minutes=30,search_days=0)).json()
    assert 'deadline_window_missed' in missed['reasons'] and missed['search_status']=='not_found'


def test_direct_database_application_cannot_bypass_pending_or_revoked_review(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    item,_ = proposal(client,f,'policy',{})
    psycopg = pytest.importorskip('psycopg')
    query = """INSERT INTO ago_calendar_changes(id,tenant_id,proposal_id,actor_id,revision,result)
               VALUES(%s,%s,%s,%s,1,'{}')"""
    params = (str(uuid4()),info['tenant'],item['id'],info['founder_id'])
    with pytest.raises(psycopg.errors.RaiseException,match='Independent'):
        with info['db'].transaction():
            info['db'].execute(query,params)
    decide(client,r,item['approval_id'])
    info['db'].execute('UPDATE ago_users SET active=false WHERE tenant_id=%s AND id=%s',(info['tenant'],info['reviewer_id']))
    with pytest.raises(psycopg.errors.RaiseException,match='Independent'):
        with info['db'].transaction():
            info['db'].execute(query,params)
    post(client,BASE+'/governance/apply',f,{'proposal_id':item['id']},expected=403)


def test_foreign_scope_and_foreign_event_are_rejected_without_disclosure(case):
    client,h,info = case
    f = h['founder']
    for command,spec in [('policy',dict(scope_kind='employee',scope_id=str(uuid4()))),
                         ('window',window(scope_kind='department',scope_id=str(uuid4()))),
                         ('event_link',dict(event_id=str(uuid4()))),
                         ('reschedule',dict(event_id=str(uuid4()),starts_at=window()['starts_at'],ends_at=window()['ends_at']))]:
        post(client,BASE+'/governance/proposals',f,dict(command=command,specification=spec,
            rationale='No cross-tenant sources',base_revision=0,operation_key=str(uuid4())),expected=403)
    for command in ('window_cancel','event_link','reschedule'):
        post(client,BASE+'/governance/proposals',f,dict(command=command,specification={},
            rationale='Malformed input rejected',base_revision=0,operation_key=str(uuid4())),expected=400)


def test_fiscal_execution_bounds_and_support_emergency_coverage_are_not_authority(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    worker = employee(client,f,department(client,f))
    now = datetime.now(timezone.utc)
    item,_ = proposal(client,f,'policy',dict(scope_kind='employee',scope_id=worker,
        support_start='00:00',support_end='24:00',emergency_reviewer_ids=[info['reviewer_id']]))
    apply(client,f,r,item)
    fiscal,_ = proposal(client,f,'window',window('budget',now+timedelta(hours=1),now+timedelta(hours=5)))
    apply(client,f,r,fiscal)
    result = client.get(BASE+'/eligibility',headers=f,params=dict(employee_id=worker,at=now.isoformat(),search_days=0)).json()
    assert result['support_coverage_available'] and result['emergency_review_available']
    assert 'outside_budget_window' in result['reasons'] and not result['eligible']
    assert result['approval_still_required'] and not result['authority_changed']


def test_rsvp_replacement_invites_and_exact_source_history(case):
    client,h,info = case
    f,r = h['founder'],h['reviewer']
    start = datetime.now(timezone.utc)+timedelta(days=2)
    original = event(client,f,start,start+timedelta(hours=1),employee_ids=[info['reviewer_id']])
    post(client,BASE+'/'+original+'/rsvp',r,dict(response='accepted'))
    candidate,_ = proposal(client,f,'reschedule',dict(event_id=original,starts_at=(start+timedelta(days=1)).isoformat(),ends_at=(start+timedelta(days=1,hours=1)).isoformat()))
    result = apply(client,f,r,candidate)
    replacement = result['result']['rescheduled'][0]['replacement_id']
    assert client.get(BASE+'/'+original+'/history',headers=r).json()[-1]['event']=='cancelled'
    invites = client.get(BASE+'/'+replacement+'/attendees',headers=r).json()
    assert invites[0]['response'] == 'invited'
    post(client,BASE+'/'+replacement+'/rsvp',r,dict(response='accepted'))
    assert client.get(BASE+'/'+replacement+'/history',headers=r).json()[-1]['event']=='accepted'
