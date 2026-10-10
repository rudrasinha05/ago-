"""Private bytes, cache integrity, offline failure and strict HTTP contracts."""
from __future__ import annotations

import hashlib
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from ago import api_m2
from ago.main import create_app
from ago.repository_ports import DatabaseStorePort, SecurityControlsPort
from ago.security import Principal
from ago.storage_adapters import (
    MAX_BYTES, PrivateObjects, StorageUnavailable, TraversalCache, normalized, offline_encoder,
)


def test_private_objects_exact_bytes_atomic_exclusive_and_hash_failure(tmp_path):
    objects = PrivateObjects(tmp_path)
    tenant, identifier = str(uuid4()), str(uuid4())
    content = b'%PDF-1.7\nprivate\x00bytes'
    digest = hashlib.sha256(content).hexdigest()
    objects.write(tenant, identifier, content)
    assert objects.read(tenant, identifier, digest, len(content)) == content
    with pytest.raises(FileExistsError):
        objects.write(tenant, identifier, b'replace')
    with pytest.raises(StorageUnavailable):
        objects.read(tenant, identifier, '0' * 64, len(content))
    with pytest.raises(StorageUnavailable):
        objects.read(str(uuid4()), identifier, digest, len(content))
    objects.remove(tenant, identifier)
    objects.remove(tenant, identifier)
    assert not list((tmp_path / tenant).glob('.pending-*'))


def test_private_objects_reject_path_traversal_symlinks_and_oversize(tmp_path):
    objects = PrivateObjects(tmp_path)
    tenant, identifier = str(uuid4()), str(uuid4())
    for bad in ('../../escape', '/etc/passwd'):
        with pytest.raises(ValueError):
            objects.write(bad, identifier, b'x')
    for content in (b'', b'x' * (MAX_BYTES + 1)):
        with pytest.raises(ValueError):
            objects.write(tenant, identifier, content)
    external = tmp_path / 'external'
    external.mkdir()
    (tmp_path / tenant).symlink_to(external, target_is_directory=True)
    with pytest.raises(OSError):
        objects.write(tenant, identifier, b'x')
    (tmp_path / tenant).unlink()
    (tmp_path / tenant).mkdir()
    (tmp_path / tenant / identifier).symlink_to('/etc/passwd')
    with pytest.raises(StorageUnavailable):
        objects.read(tenant, identifier, '0' * 64, 1)


@pytest.mark.parametrize('vector', [[0.0] * 384, [float('nan')] * 384,
                                   [float('inf')] * 384, [1.0] * 383,
                                   [1e308] * 384, ['invalid'] * 384])
def test_invalid_vectors_fail(vector):
    with pytest.raises(ValueError):
        normalized(vector)


def test_no_model_configuration_never_downloads(monkeypatch):
    monkeypatch.delenv('AGO_EMBEDDING_DIR', raising=False)
    with pytest.raises(StorageUnavailable, match='not configured'):
        offline_encoder()


def test_traversal_cache_signed_tenant_version_keys_and_invalid_payload(monkeypatch):
    monkeypatch.setenv('AGO_SESSION_SECRET', 'cache-test-key-with-at-least-32-bytes')
    monkeypatch.delenv('AGO_GRAPH_REDIS_URL', raising=False)
    class Cache:
        def __init__(self):
            self.values = {}
        def setex(self, key, ttl, payload):
            assert ttl == 60
            self.values[key] = payload
        def get(self, key):
            return self.values.get(key)
        def close(self):
            pass
    cache = TraversalCache()
    cache.client = Cache()
    key = cache.key(str(uuid4()), 1, ('root', 2, 100, 'both'))
    cache.put(key, {'nodes': [], 'edges': []})
    assert cache.get(key) == {'nodes': [], 'edges': []}
    other = cache.key(str(uuid4()), 2, ('root', 2, 100, 'both'))
    cache.client.values[other] = cache.client.values[key]
    assert cache.get(other) is None
    cache.client.values[key] = b'forged\n{"nodes":["private"]}'
    assert cache.get(key) is None
    class Offline(Cache):
        def get(self, key):
            raise ConnectionError('disposable outage')
    cache.client = Offline()
    assert cache.get(key) is None


def test_http_authority_fields_strict_limits_and_safe_provider_failure(monkeypatch):
    monkeypatch.setenv('AGO_ENVIRONMENT', 'development')
    actor = Principal(str(uuid4()), str(uuid4()), ('founder',))
    class Grants:
        def __init__(self, _db):
            pass
        def permitted(self, actor, permission, tenant):
            return True
    class Store:
        def __init__(self, _db):
            pass
        def search(self, **kwargs):
            assert kwargs['tenant_id'] == actor.tenant_id
            raise StorageUnavailable('/private/path secret should never appear')
    app = create_app()
    app.dependency_overrides[api_m2.authenticated] = lambda: actor
    app.dependency_overrides[api_m2.db_connection] = lambda: object()
    app.state.repository_overrides = {SecurityControlsPort: Grants, DatabaseStorePort: Store}
    with TestClient(app) as client:
        for payload in ({'query': 'meaning', 'tenant_id': str(uuid4())},
                        {'query': 'meaning', 'limit': True}, {'query': 'meaning', 'limit': 51}):
            assert client.post('/v1/knowledge/search', json=payload).status_code == 422
        response = client.post('/v1/knowledge/search', json={'query': 'meaning'})
        assert response.status_code == 503
        assert '/private' not in response.text and 'secret' not in response.text
