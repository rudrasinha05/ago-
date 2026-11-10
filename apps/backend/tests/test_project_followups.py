"""Durable failure ownership, feedback, calendar and replay boundaries (real PostgreSQL)."""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from ago.calendar_store import CalendarStore
from ago.stage_progression import StageProgression
from test_m7_http_postgres import case as case, post
from test_project_advance import company as company


def followups(c):
    return c.client.get(c.url, headers=c.founder).json()['followups']


def test_qa_feedback_reaches_same_worker_and_resolves_only_after_qa(company):
    c = company
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    old = str(c.stage('discovery')['task_id'])
    c.qa_answer = 'FINDINGS: Add a concrete acceptance checklist.\nQA_VERDICT: FAIL'
    failed = post(c.client, c.advance, c.founder)
    routed = failed['decision']['followup']
    assert routed['source_task_id'] == old
    assert routed['work_task_id'] == str(c.stage('discovery')['task_id']) != old
    assert routed['owner_id'] == str(c.stage('discovery')['assignee_id'])
    assert routed['status'] == 'assigned' and routed['executed'] is False
    assert 'acceptance checklist' in routed['feedback']
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    assert 'acceptance checklist' in c.seen[-1]['recovery_feedback']
    assert 'stage deliverable' in c.seen[-1]['failed_work']
    assert followups(c)[0]['status'] == 'assigned'
    c.qa_answer = 'QA_VERDICT: PASS'
    post(c.client, c.advance, c.founder)
    assert followups(c)[0]['status'] == 'resolved'
    assert c.db.execute('SELECT verdict FROM ago_task_reviews WHERE task_id=%s', (old,)).fetchone()['verdict'] == 'fail'
    notice = c.db.execute("SELECT body,employee_id FROM ago_company_chat WHERE tenant_id=%s "
                          "AND author_name='AGO work routing'", (c.tenant,)).fetchall()
    assert len(notice) == 1 and '@Research Analyst' in notice[0]['body']


def test_unknown_failure_is_assigned_to_founder_without_replay_or_notice_spam(company):
    c = company
    c.failures = [ValueError('private error must not appear')]
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    for _ in range(3):
        reply = post(c.client, c.advance, c.founder)
        assert reply['needs_founder']
    rows = followups(c)
    assert len(rows) == 1 and rows[0]['owner_id'] == c.info['founder_id']
    assert rows[0]['status'] == 'blocked'
    assert 'private error' not in str(rows)
    assert len(c.seen) == 1 and c.recoveries('discovery') == []


def test_calendar_wait_is_durable_deduplicated_and_does_not_run(company, monkeypatch):
    c = company
    for _ in range(2):
        post(c.client, c.advance, c.founder)
    due = datetime.now(timezone.utc) + timedelta(hours=1)
    def unavailable(*args, **kwargs):
        raise PermissionError('Calendar blocks execution')
    monkeypatch.setattr(CalendarStore, 'require_execution', unavailable)
    monkeypatch.setattr(CalendarStore, 'eligibility', lambda *a, **k: {
        'eligible': False, 'reasons': ['outside_work_window'], 'next_eligible_at': due})
    first = post(c.client, c.advance, c.founder)
    assert first['followup']['status'] == 'scheduled'
    assert first['followup']['owner_id'] == str(c.stage('discovery')['assignee_id'])
    for _ in range(3):
        held = post(c.client, c.advance, c.founder)
        assert held['scheduled'] and not held['progressed'] and not held['needs_founder']
        assert held['followup']['id'] == first['followup']['id']
    assert len(followups(c)) == 1 and c.seen == []


def test_calendar_without_slot_routes_to_manager(company, monkeypatch):
    c = company
    for _ in range(2):
        post(c.client, c.advance, c.founder)
    def unavailable(*args, **kwargs):
        raise PermissionError('Calendar blocks execution')
    monkeypatch.setattr(CalendarStore, 'require_execution', unavailable)
    monkeypatch.setattr(CalendarStore, 'eligibility', lambda *a, **k: {
        'eligible': False, 'reasons': ['outside_work_window'], 'next_eligible_at': None})
    held = post(c.client, c.advance, c.founder)
    assert held['needs_founder'] and held['followup']['owner_id'] == c.people['CEO']
    assert '14 days' in held['followup']['feedback'] and c.seen == []


def test_qa_attempt_limit_survives_new_requests_and_requires_explicit_tester(company):
    c = company
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    c.qa_answer = 'No clear verdict.'
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    for _ in range(2):
        held = post(c.client, c.advance, c.founder)
        assert held['needs_founder'] and held['followup']['code'] == 'qa_attempt_limit'
    assert len(c.qa_prompts) == 3
    post(c.client, c.url+'/stages/discovery/ai-qa', c.founder,
         {'operation_key': str(uuid4())}, expected=403)
    assert len(c.qa_prompts) == 3
    c.qa_answer = 'QA_VERDICT: PASS'
    resumed = post(c.client, c.url+'/stages/discovery/ai-qa', c.founder, {
        'operation_key': str(uuid4()), 'qa_employee_id': c.people['QA Specialist']})
    assert resumed['verdict'] == 'pass' and len(c.qa_prompts) == 4
    assert all(f['status'] == 'resolved' for f in followups(c))


def test_followup_rejects_foreign_task_and_preserves_evidence(company):
    c = company
    service = StageProgression(c.db)
    args = dict(tenant_id=c.tenant, founder_id=c.info['founder_id'], project_id=c.id,
                stage='discovery', code='test_blocker', feedback='Investigate recorded evidence')
    with pytest.raises(PermissionError):
        service.route_followup(**args, source_task_id=str(uuid4()))
    item = service.route_followup(**args)
    assert service.route_followup(**args)['id'] == item['id']
    import psycopg
    with pytest.raises(psycopg.Error), c.db.transaction():
        c.db.execute('UPDATE ago_project_followups SET feedback=%s WHERE id=%s', ('altered', item['id']))
    with pytest.raises(psycopg.Error), c.db.transaction():
        c.db.execute('DELETE FROM ago_project_followups WHERE id=%s', (item['id'],))


def test_project_lock_prevents_competing_session_and_releases_after_error(company):
    import os
    import psycopg
    from psycopg.rows import dict_row
    c = company
    first = StageProgression(c.db)
    with psycopg.connect(os.environ['AGO_TEST_POSTGRES_DSN'], row_factory=dict_row) as other:
        second = StageProgression(other)
        with pytest.raises(RuntimeError):
            with first.advance_guard(tenant_id=c.tenant, project_id=c.id) as acquired:
                assert acquired
                with second.advance_guard(tenant_id=c.tenant, project_id=c.id) as competing:
                    assert not competing
                raise RuntimeError('simulated interruption')
        with second.advance_guard(tenant_id=c.tenant, project_id=c.id) as acquired:
            assert acquired


def test_safe_model_retry_is_assigned_but_waits_for_backoff(company):
    c = company
    c.failures = [TimeoutError('model')]
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    routed = followups(c)[0]
    assert routed['status'] == 'scheduled' and routed['code'] == 'retry'
    assert routed['owner_id'] == str(c.stage('discovery')['assignee_id'])
    for _ in range(2):
        post(c.client, c.advance, c.founder)
    assert post(c.client, c.advance, c.founder)['scheduled']
    assert len(c.seen) == 1 and len(c.recoveries('discovery')) == 1


def test_qa_credit_blocker_belongs_to_founder_and_spends_nothing(company):
    c = company
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    c.db.execute('DELETE FROM ago_credit_budgets WHERE tenant_id=%s', (c.tenant,))
    held = post(c.client, c.advance, c.founder)
    assert held['needs_founder'] and held['followup']['code'] == 'credit_budget_missing'
    assert held['followup']['owner_id'] == c.info['founder_id']
    assert c.qa_prompts == [] and len(followups(c)) == 1


def test_continuation_error_keeps_recorded_work_and_assigns_manager(company, monkeypatch):
    c = company
    for _ in range(3):
        post(c.client, c.advance, c.founder)
    def unavailable(*args, **kwargs):
        raise RuntimeError('private backend detail')
    monkeypatch.setattr(StageProgression, 'continue_project', unavailable)
    reviewed = post(c.client, c.advance, c.founder)
    assert reviewed['qa_verdict'] == 'pass'
    followup = reviewed['decision']['followup']
    assert followup['owner_id'] == c.people['CEO']
    assert followup['code'] == 'continuation_error'
    assert 'private backend detail' not in str(reviewed)
    assert c.stage('discovery')['status'] == 'completed'
    assert c.stage('architecture')['task_id'] is None
