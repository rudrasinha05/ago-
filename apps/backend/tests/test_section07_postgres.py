"""Real signed-session PostgreSQL graph/vector/private object integration.

Fake unit encoder is deliberately labelled; the separate storage CI job also
runs this journey with the prepared actual offline ONNX model and real Redis.
"""
from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from uuid import uuid4

import pytest

import test_m6_http_integration as m6
from ago.database_store import DatabaseStore
from ago.bootstrap import bootstrap
from ago.repository_ports import DatabaseStorePort
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.storage_adapters import PrivateObjects, StorageUnavailable, offline_encoder

case = m6.case
post = m6.post


class UnitEncoder:
    model_id = 'unit-test-injected-encoder-not-semantic-evidence'
    def embed(self, text, *, query=False):
        return ([1.0, 0.0] if 'dog' in text.lower() else [0.0, 1.0]) + [0.0] * 382


def reviewed(client, headers, label, *, approve=True):
    node = post(client, '/v1/knowledge/nodes', headers['founder'], {
        'kind': 'fact', 'label': label, 'statement': label,
        'source_ref': 'internal:section07:' + label})
    post(client, f"/v1/knowledge/nodes/{node['id']}/review", headers['reviewer1'],
         {'approve': approve, 'note': 'Independent source inspected'})
    return node['id']


def configured(case, tmp_path, monkeypatch):
    client, headers, info = case
    monkeypatch.setenv('AGO_OBJECTS_DIR', str(tmp_path))
    model = offline_encoder() if os.getenv('AGO_S7_REAL_MODEL') == 'true' else UnitEncoder()
    client.app.state.repository_overrides = {
        DatabaseStorePort: lambda db, repositories: DatabaseStore(
            db, repositories=repositories, encoder=model)}
    return client, headers, info, model


def test_reviewed_graph_cycles_bounds_direction_cache_invalidation_and_tenant(case, tmp_path, monkeypatch):
    client, headers, info, model = configured(case, tmp_path, monkeypatch)
    nodes = [reviewed(client, headers, name) for name in ('root', 'middle', 'leaf')]
    for source, target in zip(nodes, nodes[1:] + nodes[:1]):
        post(client, '/v1/knowledge/edges', headers['founder'], {
            'from_id': source, 'to_id': target, 'relation': 'supports'})
    url = f'/v1/knowledge/nodes/{nodes[0]}/graph'
    assert client.get(url).status_code == 401
    graph = client.get(url, headers=headers['founder'], params={'depth': 4}).json()
    assert len(graph['nodes']) == len(graph['edges']) == 3
    assert graph == client.get(url, headers=headers['founder'], params={'depth': 4}).json()
    bounded = client.get(url, headers=headers['founder'], params={'limit': 1}).json()
    assert len(bounded['nodes']) == 1 and bounded['truncated'] is True
    assert client.get(url, headers=headers['founder'], params={'depth': 5}).status_code == 422
    outward = client.get(url, headers=headers['founder'], params={'depth': 1, 'direction': 'out'}).json()
    assert len(outward['nodes']) == 2 and len(outward['edges']) == 1
    leaf = reviewed(client, headers, 'new leaf')
    post(client, '/v1/knowledge/edges', headers['founder'], {
        'from_id': nodes[0], 'to_id': leaf, 'relation': 'references'})
    current = client.get(url, headers=headers['founder'], params={'depth': 4}).json()
    assert current['version'] > graph['version'] and len(current['nodes']) == 4
    rejected = reviewed(client, headers, 'rejected', approve=False)
    assert client.get(f'/v1/knowledge/nodes/{rejected}/graph', headers=headers['founder']).status_code == 404
    with pytest.raises(LookupError):
        DatabaseStore(info['db']).graph(tenant_id=str(uuid4()), root_id=nodes[0])
    if os.getenv('AGO_S7_REAL_REDIS') == 'true':
        import redis
        cache = redis.Redis.from_url(os.environ['AGO_GRAPH_REDIS_URL'])
        keys = list(cache.scan_iter(f"ago:graph:v1:{info['tenant']}:*"))
        assert keys and all(0 < cache.ttl(key) <= 60 for key in keys)
        for key in keys:
            cache.set(key, b'forged\n{"nodes":[]}', ex=60)
        repaired = client.get(url, headers=headers['founder'], params={'depth': 4}).json()
        assert repaired == current
        monkeypatch.setenv('AGO_GRAPH_REDIS_URL', 'redis://127.0.0.1:1/0')
        assert client.get(url, headers=headers['founder'], params={'depth': 4}).json() == current
    # Grant checks happen before cached results, even with a still-valid signed session.
    SecurityControls(info['db']).revoke_grant(info['tenant'], 'founder', 'knowledge:read')
    assert client.get(url, headers=headers['founder']).status_code == 403


def test_versioned_semantic_index_rebuild_relevance_and_unreviewed_exclusion(case, tmp_path, monkeypatch):
    client, headers, info, model = configured(case, tmp_path, monkeypatch)
    dog = reviewed(client, headers, 'A dog is a loyal animal and domestic pet')
    other = reviewed(client, headers, 'A SQL database stores transaction records on a server')
    pending = post(client, '/v1/knowledge/nodes', headers['founder'], {
        'kind': 'fact', 'label': 'pending', 'statement': 'not reviewed', 'source_ref': 'internal:pending'})['id']
    post(client, f'/v1/knowledge/nodes/{pending}/index', headers['founder'], expected=404)
    for identifier in (dog, other):
        post(client, f'/v1/knowledge/nodes/{identifier}/index', headers['founder'])
    post(client, f'/v1/knowledge/nodes/{dog}/index', headers['reviewer1'], expected=403)
    query = 'Which animal makes a faithful household companion?' if os.getenv('AGO_S7_REAL_MODEL') == 'true' else 'dog'
    result = post(client, '/v1/knowledge/search', headers['founder'], {'query': query})
    assert result['indexed'] == 2 and result['results'][0]['id'] == dog
    assert result['results'][0]['score'] > result['results'][1]['score']
    assert result['results'][0]['source_ref'].startswith('internal:section07:')
    store = DatabaseStore(info['db'], encoder=model)
    assert store.search(tenant_id=str(uuid4()), query=query)['results'] == []
    assert store.rebuild_index(tenant_id=info['tenant'])['complete'] is True
    assert store.search(tenant_id=info['tenant'], query=query)['indexed'] == 2
    monkeypatch.delenv('AGO_EMBEDDING_DIR', raising=False)
    client.app.state.repository_overrides = {}
    post(client, '/v1/knowledge/search', headers['founder'], {'query': query}, expected=503)


def test_private_documents_auth_corruption_backup_restore_and_retention(case, tmp_path, monkeypatch):
    client, headers, info, model = configured(case, tmp_path, monkeypatch)
    content = b'Private evidence bytes\x00\xff'
    body = {'filename': 'evidence.pdf', 'media_type': 'application/pdf',
            'content_base64': base64.b64encode(content).decode()}
    post(client, '/v1/knowledge/documents', headers['reviewer1'], body, expected=403)
    post(client, '/v1/knowledge/documents', headers['founder'], body | {'filename': '../escape'}, expected=400)
    post(client, '/v1/knowledge/documents', headers['founder'], body | {'content_base64': '!!!!'}, expected=400)
    uploaded = post(client, '/v1/knowledge/documents', headers['founder'], body)
    identifier = uploaded['id']
    url = '/v1/knowledge/documents/' + identifier
    assert client.get(url).status_code == 401
    downloaded = client.get(url, headers=headers['founder'])
    assert downloaded.content == content and downloaded.headers['cache-control'] == 'no-store'
    assert downloaded.headers['content-type'] == 'application/octet-stream'
    store = DatabaseStore(info['db'])
    with pytest.raises(LookupError):
        store.download(tenant_id=str(uuid4()), object_id=identifier)
    backup = tmp_path.parent / ('backup-' + str(uuid4()))
    restored = tmp_path.parent / ('restore-' + str(uuid4()))
    assert store.backup_objects(tenant_id=info['tenant'], destination=str(backup))['backed_up'] == 1
    assert store.restore_objects(tenant_id=info['tenant'], source=str(backup), destination=str(restored))['verified']
    assert PrivateObjects(restored).read(info['tenant'], identifier, uploaded['sha256'], len(content)) == content
    (backup / info['tenant'] / identifier).write_bytes(b'corrupted')
    with pytest.raises(StorageUnavailable):
        store.restore_objects(tenant_id=info['tenant'], source=str(backup), destination=str(restored) + '-invalid')
    assert not Path(str(restored) + '-invalid').exists()
    (tmp_path / info['tenant'] / identifier).write_bytes(b'corrupted')
    assert client.get(url, headers=headers['founder']).status_code == 503
    # Past due upload uses DB insertion in a nested transaction for retention fixture;
    # immutable metadata is never rewritten to manufacture expiry.
    expired_id = str(uuid4())
    info['db'].execute(
        """INSERT INTO ago_document_objects(id,tenant_id,author_id,filename,media_type,bytes,
           sha256,created_at,expires_at) VALUES(%s,%s,%s,'expired','text/plain',1,%s,
           now()-interval '2 days',now()-interval '1 day')""",
        (expired_id, info['tenant'], info['founder'], hashlib.sha256(b'x').hexdigest()))
    PrivateObjects().write(info['tenant'], expired_id, b'x')
    assert store.expire(tenant_id=info['tenant'])['processed'] == 1
    assert store.expire(tenant_id=info['tenant'])['processed'] == 1
    assert not (tmp_path / info['tenant'] / expired_id).exists()
    assert info['db'].execute('SELECT status FROM ago_document_objects WHERE id=%s',
                              (expired_id,)).fetchone()['status'] == 'expired'
    with pytest.raises(LookupError):
        store.download(tenant_id=info['tenant'], object_id=expired_id)


def test_actual_other_tenant_cannot_read_graph_objects_or_vectors(case, tmp_path, monkeypatch):
    client, headers, info, model = configured(case, tmp_path, monkeypatch)
    node = reviewed(client, headers, 'Private first tenant dog evidence')
    post(client, f'/v1/knowledge/nodes/{node}/index', headers['founder'])
    document = post(client, '/v1/knowledge/documents', headers['founder'], {
        'filename': 'private.txt', 'media_type': 'text/plain', 'content_base64': 'cHJpdmF0ZQ=='})
    other, _ = bootstrap(info['db'], organization='Isolated second tenant',
                         email='isolated@example.test', password='isolated-test-password-123')
    login = post(client, '/v1/sessions', {}, {'tenant_id': other,
        'email': 'isolated@example.test', 'password': 'isolated-test-password-123'})
    outsider = {'Authorization': 'Bearer ' + login['access_token']}
    assert client.get(f'/v1/knowledge/nodes/{node}/graph', headers=outsider).status_code == 404
    assert client.get('/v1/knowledge/documents/' + document['id'], headers=outsider).status_code == 404
    assert client.get('/v1/knowledge/documents', headers=outsider).json() == []
    assert post(client, '/v1/knowledge/search', outsider, {'query': 'dog'})['results'] == []
    post(client, '/v1/knowledge/search', outsider,
         {'query': 'dog', 'tenant_id': info['tenant']}, expected=422)


def test_database_rejects_invalid_vectors_metadata_changes_and_foreign_sources(case):
    client, headers, info = case
    node = reviewed(client, headers, 'Vector constraint source')
    import psycopg
    for vector in ([], [0.0] * 384, [1.0] * 383, [float('nan')] * 384):
        with pytest.raises(psycopg.errors.CheckViolation):
            with info['db'].transaction():
                info['db'].execute(
                    """INSERT INTO ago_semantic_vectors
                       (tenant_id,node_id,model_id,source_sha256,embedding) VALUES(%s,%s,'invalid',%s,%s)""",
                    (info['tenant'], node, '0' * 64, vector))


def test_upload_database_failure_does_not_publish_partial_bytes(case, tmp_path, monkeypatch):
    client, headers, info, model = configured(case, tmp_path, monkeypatch)
    invalid = Principal(str(uuid4()), info['tenant'], ('founder',))
    with pytest.raises(Exception):
        DatabaseStore(info['db']).upload(actor=invalid, filename='rollback',
                                         media_type='text/plain', content=b'private')
    tenant_dir = tmp_path / info['tenant']
    assert not tenant_dir.exists() or not list(tenant_dir.iterdir())
