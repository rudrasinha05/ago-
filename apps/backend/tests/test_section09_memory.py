"""Scope, correction/forgetting and actual offline semantic memory journeys."""
import os
from uuid import uuid4

import pytest
import test_m6_http_integration as m6
from test_section07_postgres import UnitEncoder, reviewed

from ago.goals import GoalStore
from ago.memory_policies import extractive_summary, validate_memory
from ago.repository_ports import SemanticMemoryStorePort
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.semantic_memory_store import SemanticMemoryStore
from ago.storage_adapters import offline_encoder

case = m6.case
post = m6.post
URL = '/v1/knowledge/memory'


@pytest.mark.parametrize('scope', ['employee', 'department', 'project', 'company'])
def test_explicit_scopes(scope):
    validate_memory(scope, str(uuid4()), 'working', 'Experience', 'internal:test', 24)


@pytest.mark.parametrize('kind,hours', [('working', 25), ('working', True), ('episodic', 8761), ('unknown', 1)])
def test_retention_never_silently_widens(kind, hours):
    with pytest.raises(ValueError):
        validate_memory('employee', str(uuid4()), kind, 'Experience', 'internal:test', hours)


def test_extractive_summary_does_not_invent_facts():
    assert extractive_summary([{'content': 'First exact account'}, {'content': 'Second exact account'}]) == 'First exact account\nSecond exact account'


def setup(case):
    client, headers, info = case
    model = offline_encoder() if os.getenv('AGO_S7_REAL_MODEL') == 'true' else UnitEncoder()
    client.app.state.repository_overrides = {SemanticMemoryStorePort: lambda db, repositories:
        SemanticMemoryStore(db, repositories=repositories, encoder=model)}
    return client, headers, info, model


def create(client, headers, info, content, **kwargs):
    return post(client, URL, headers['founder'], {'scope': 'employee', 'scope_id': info['founder'],
        'kind': 'episodic', 'content': content, 'source_ref': 'internal:experience:section09', **kwargs})


def test_private_company_department_project_and_live_membership(case):
    client, headers, info, _ = setup(case)
    private = create(client, headers, info, 'private experience')
    assert client.get(URL + '/' + private['id'], headers=headers['reviewer1']).status_code == 404
    shared = create(client, headers, info, 'company account', scope='company', scope_id=info['tenant'])
    assert client.get(URL + '/' + shared['id'], headers=headers['reviewer1']).status_code == 200
    department = create(client, headers, info, 'department account', scope='department', scope_id=info['executive'])
    assert client.get(URL + '/' + department['id'], headers=headers['reviewer1']).status_code == 404
    invalid = {'scope': 'department', 'scope_id': info['research'], 'kind': 'episodic',
               'content': 'scope spoof', 'source_ref': 'internal:test'}
    post(client, URL, headers['founder'], invalid, expected=403)
    goal = GoalStore(info['db']).create(tenant_id=info['tenant'], created_by=info['founder'], title='Memory project')
    membership = URL + '/projects/' + goal + '/members'
    post(client, membership, headers['founder'], {'user_id': info['founder'], 'member': True})
    project = create(client, headers, info, 'project experience', scope='project', scope_id=goal)
    assert client.get(URL + '/' + project['id'], headers=headers['reviewer1']).status_code == 404
    post(client, membership, headers['founder'], {'user_id': info['reviewer1'], 'member': True})
    assert client.get(URL + '/' + project['id'], headers=headers['reviewer1']).status_code == 200
    post(client, membership, headers['reviewer1'], {'user_id': info['reviewer2'], 'member': True}, expected=403)
    post(client, membership, headers['founder'], {'user_id': info['reviewer1'], 'member': False})
    assert client.get(URL + '/' + project['id'], headers=headers['reviewer1']).status_code == 404
    with pytest.raises(PermissionError):
        SemanticMemoryStore(info['db']).get(actor=Principal(info['founder'], str(uuid4()), ('founder',)), memory_id=private['id'])


def test_semantic_search_correction_consolidation_forgetting_and_provenance(case):
    client, headers, info, model = setup(case)
    evidence = reviewed(client, headers, 'Memory supporting source')
    dog = create(client, headers, info, 'A dog is a loyal animal and domestic pet', knowledge_id=evidence)
    sql = create(client, headers, info, 'A SQL database stores transaction records on a server')
    for row in (dog, sql):
        post(client, URL + '/' + row['id'] + '/index', headers['founder'])
    query = 'Which animal makes a faithful household companion?' if os.getenv('AGO_S7_REAL_MODEL') == 'true' else 'dog'
    result = post(client, URL + '/search', headers['founder'], {'query': query})
    assert result['indexed'] == 2 and result['results'][0]['id'] == dog['id']
    assert result['results'][0]['score'] > result['results'][1]['score']
    assert post(client, URL + '/search', headers['reviewer1'], {'query': query})['results'] == []
    summary = post(client, URL + '/consolidate', headers['founder'], {'memory_ids': [dog['id'], sql['id']]})
    assert len(summary['sources']) == 2 and summary['scope'] == 'employee'
    assert summary['expires_at'] <= min(dog['expires_at'], sql['expires_at'])
    assert client.get(URL + '/' + summary['id'], headers=headers['reviewer1']).status_code == 404
    changed = post(client, URL + '/' + dog['id'] + '/correct', headers['founder'],
        {'content': 'Corrected account about a computer server', 'expected_revision': 1, 'reason': 'Source corrected'})
    assert changed['revision'] == 2
    assert client.get(URL + '/' + summary['id'], headers=headers['founder']).status_code == 404
    post(client, URL + '/' + dog['id'] + '/correct', headers['founder'],
        {'content': 'Stale write', 'expected_revision': 1, 'reason': 'Conflict'}, expected=400)
    assert post(client, URL + '/search', headers['founder'], {'query': query})['indexed'] == 1
    post(client, URL + '/' + dog['id'] + '/index', headers['founder'])
    post(client, URL + '/' + dog['id'] + '/forget', headers['founder'], {'reason': 'Privacy request'})
    assert client.get(URL + '/' + dog['id'], headers=headers['founder']).status_code == 404
    assert info['db'].execute('SELECT 1 FROM ago_memory_vectors WHERE memory_id=%s', (dog['id'],)).fetchone() is None
    rows = info['db'].execute('SELECT content,source_ref,knowledge_id FROM ago_scoped_memories WHERE id=ANY(%s::uuid[])',
                             ([dog['id'], summary['id']],)).fetchall()
    assert all(r['content'] is None and r['source_ref'] == 'redacted' and r['knowledge_id'] is None for r in rows)
    audit = info['db'].execute("SELECT metadata FROM ago_security_audit WHERE tenant_id=%s AND action LIKE 'memory.%%'", (info['tenant'],)).fetchall()
    assert audit and 'loyal animal' not in str(audit)
    assert model.model_id


def test_expiry_immediate_denial_cleanup_and_evidence_rejection(case):
    client, headers, info, _ = setup(case)
    working = create(client, headers, info, 'Transient working context', kind='working', retention_hours=1)
    post(client, URL, headers['founder'], {'scope': 'employee', 'scope_id': info['founder'],
        'kind': 'working', 'content': 'Too long', 'source_ref': 'internal:test', 'retention_hours': 25}, expected=400)
    create_body = {'scope': 'company', 'scope_id': info['tenant'], 'kind': 'episodic',
                  'content': 'Unverified link', 'source_ref': 'internal:test', 'knowledge_id': str(uuid4())}
    post(client, URL, headers['founder'], create_body, expected=403)
    info['db'].execute("UPDATE ago_scoped_memories SET created_at=now()-interval '2 hours',expires_at=now()-interval '1 hour' WHERE id=%s", (working['id'],))
    assert client.get(URL + '/' + working['id'], headers=headers['founder']).status_code == 404
    post(client, URL + '/expire', headers['reviewer1'], expected=403)
    assert post(client, URL + '/expire', headers['founder'])['scrubbed'] == 1
    assert post(client, URL + '/expire', headers['founder'])['scrubbed'] == 0
    body = {'scope': 'employee', 'scope_id': info['founder'], 'kind': 'episodic', 'content': 'spoof', 'source_ref': 'internal:test'}
    post(client, URL, headers['founder'], body | {'owner_id': info['reviewer1']}, expected=422)
    assert client.post(URL, json=body).status_code == 401
    SecurityControls(info['db']).revoke_grant(info['tenant'], 'founder', 'memory:read')
    post(client, URL + '/search', headers['founder'], {'query': 'dog'}, expected=403)


def test_consolidation_cannot_promote_private_scope(case):
    client, headers, info, _ = setup(case)
    private = create(client, headers, info, 'Private exact account')
    company = create(client, headers, info, 'Shared exact account', scope='company', scope_id=info['tenant'])
    post(client, URL + '/consolidate', headers['founder'], {'memory_ids': [private['id'], company['id']]}, expected=403)
    post(client, URL + '/consolidate', headers['founder'], {'memory_ids': [private['id'], private['id']]}, expected=400)
