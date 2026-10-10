"""Section 7 context-owned PostgreSQL graph, vector and document repository.

Derived indexes/cache never authorize a read. Public HTTP adapters enforce
knowledge grants before resolving this trusted repository; tenant is server derived.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.security import Principal
from ago.storage_adapters import (
    MAX_BYTES, PrivateObjects, StorageUnavailable, TraversalCache, normalized, offline_encoder,
)

MAX_VECTORS = 2000
MAX_TENANT_BYTES = 64 * 1024 * 1024


class DatabaseStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None,
                 encoder=None, objects=None, cache=None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)
        self._encoder = encoder
        self._objects = objects
        self.cache = cache or TraversalCache()

    def _bytes(self):
        return self._objects or PrivateObjects()

    def _model(self):
        return self._encoder or offline_encoder()

    def _version(self, tenant_id):
        row = self.db.execute('SELECT version FROM ago_knowledge_versions WHERE tenant_id=%s',
                              (tenant_id,)).fetchone()
        return row['version'] if row else 0

    def graph(self, *, tenant_id: str, root_id: str, depth: int = 2,
              limit: int = 100, direction: str = 'both') -> dict:
        tenant_id, root_id = str(UUID(tenant_id)), str(UUID(root_id))
        if (type(depth) is not int or type(limit) is not int or not 0 <= depth <= 4
                or not 1 <= limit <= 200 or direction not in {'both', 'out', 'in'}):
            raise ValueError('Invalid bounded graph request')
        version = self._version(tenant_id)
        root = self.db.execute(
            """SELECT id,kind,label,statement,source_ref FROM ago_knowledge_nodes
               WHERE tenant_id=%s AND id=%s AND status='verified'""",
            (tenant_id, root_id)).fetchone()
        if not root:
            raise LookupError('Verified knowledge root not found')
        key = self.cache.key(tenant_id, version, (root_id, depth, limit, direction))
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        nodes = {root_id: dict(root)}
        edges = {}
        frontier = [root_id]
        truncated = False
        work = 0
        with self.db.transaction():
            for _ in range(depth):
                if not frontier:
                    break
                rows = self.db.execute(
                    """SELECT e.id,e.from_id,e.to_id,e.relation,
                              s.kind AS sk,s.label AS sl,s.statement AS ss,s.source_ref AS sr,
                              t.kind AS tk,t.label AS tl,t.statement AS ts,t.source_ref AS tr
                       FROM ago_knowledge_edges e
                       JOIN ago_knowledge_nodes s ON s.tenant_id=e.tenant_id AND s.id=e.from_id
                       JOIN ago_knowledge_nodes t ON t.tenant_id=e.tenant_id AND t.id=e.to_id
                       WHERE e.tenant_id=%s AND s.status='verified' AND t.status='verified'
                         AND ((%s IN ('both','out') AND e.from_id=ANY(%s::uuid[]))
                           OR (%s IN ('both','in') AND e.to_id=ANY(%s::uuid[])))
                       ORDER BY e.id LIMIT %s""",
                    (tenant_id, direction, frontier, direction, frontier, 2001 - work)
                ).fetchall()
                if len(rows) > 2000 - work:
                    truncated = True
                    rows = rows[:2000 - work]
                work += len(rows)
                following = []
                for row in rows:
                    source, target = str(row['from_id']), str(row['to_id'])
                    missing = [i for i in (source, target) if i not in nodes]
                    if len(nodes) + len(missing) > limit:
                        truncated = True
                        continue
                    for identifier in missing:
                        prefix = 's' if identifier == source else 't'
                        nodes[identifier] = {'id': identifier, 'kind': row[prefix + 'k'],
                                             'label': row[prefix + 'l'],
                                             'statement': row[prefix + 's'],
                                             'source_ref': row[prefix + 'r']}
                        following.append(identifier)
                    edges[str(row['id'])] = {'id': row['id'], 'from_id': source,
                                             'to_id': target, 'relation': row['relation']}
                frontier = following
                if work >= 2000:
                    truncated = True
                    break
        # Uniform JSON-safe shape whether delivered by Redis or PostgreSQL.
        result = json.loads(json.dumps({'root_id': root_id, 'version': version,
                            'nodes': [nodes[k] for k in sorted(nodes)],
                            'edges': [edges[k] for k in sorted(edges)],
                            'depth': depth, 'truncated': truncated}, default=str))
        if self._version(tenant_id) == version:
            self.cache.put(key, result)
        return result

    def index_node(self, *, tenant_id: str, node_id: str) -> dict:
        tenant_id, node_id = str(UUID(tenant_id)), str(UUID(node_id))
        node = self.db.execute(
            """SELECT label,statement FROM ago_knowledge_nodes
               WHERE tenant_id=%s AND id=%s AND status='verified'""",
            (tenant_id, node_id)).fetchone()
        if node is None:
            raise LookupError('Verified knowledge node not found')
        model = self._model()
        text = node['label'] + '\n' + node['statement']
        vector = normalized(model.embed(text))
        digest = hashlib.sha256(text.encode()).hexdigest()
        with self.db.transaction():
            # Serialize derived-index capacity decisions per tenant.
            self.db.execute('SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE', (tenant_id,))
            count = self.db.execute(
                """SELECT count(*) AS n FROM ago_semantic_vectors
                   WHERE tenant_id=%s AND model_id=%s AND node_id<>%s""",
                (tenant_id, model.model_id, node_id)).fetchone()['n']
            if count >= MAX_VECTORS:
                raise ValueError('Semantic index capacity reached')
            self.db.execute(
                """INSERT INTO ago_semantic_vectors(tenant_id,node_id,model_id,source_sha256,embedding)
                   VALUES(%s,%s,%s,%s,%s) ON CONFLICT(tenant_id,model_id,node_id)
                   DO UPDATE SET source_sha256=excluded.source_sha256,
                     embedding=excluded.embedding,indexed_at=now()""",
                (tenant_id, node_id, model.model_id, digest, vector))
        return {'node_id': node_id, 'model_id': model.model_id, 'indexed': True}

    def search(self, *, tenant_id: str, query: str, limit: int = 10) -> dict:
        UUID(tenant_id)
        if type(limit) is not int or not 1 <= limit <= 50 or not 1 <= len(query.strip()) <= 1000:
            raise ValueError('Invalid semantic query')
        model = self._model()
        vector = normalized(model.embed(query, query=True))
        rows = self.db.execute(
            """SELECT n.id,n.kind,n.label,n.statement,n.source_ref,
                      v.embedding,v.source_sha256
               FROM ago_semantic_vectors v JOIN ago_knowledge_nodes n
                 ON n.tenant_id=v.tenant_id AND n.id=v.node_id
               WHERE v.tenant_id=%s AND v.model_id=%s AND n.status='verified'
               ORDER BY n.id LIMIT 2001""", (tenant_id, model.model_id)).fetchall()
        if len(rows) > MAX_VECTORS:
            raise StorageUnavailable('Semantic index exceeds configured capacity')
        results = []
        for row in rows:
            text = row['label'] + '\n' + row['statement']
            if hashlib.sha256(text.encode()).hexdigest() != row['source_sha256']:
                raise StorageUnavailable('Semantic source integrity unavailable')
            embedding = normalized(row['embedding'])
            results.append({k: str(row[k]) for k in ('id', 'kind', 'label', 'statement', 'source_ref')}
                           | {'score': sum(a * b for a, b in zip(vector, embedding))})
        results.sort(key=lambda item: (-item['score'], item['id']))
        return {'model_id': model.model_id, 'method': 'bounded-exact-cosine',
                'indexed': len(rows), 'results': results[:limit]}

    def rebuild_index(self, *, tenant_id: str) -> dict:
        UUID(tenant_id)
        model = self._model()
        nodes = self.db.execute(
            """SELECT id FROM ago_knowledge_nodes WHERE tenant_id=%s AND status='verified'
               ORDER BY id LIMIT 2001""", (tenant_id,)).fetchall()
        if len(nodes) > MAX_VECTORS:
            raise ValueError('Tenant exceeds bounded semantic index capacity')
        for node in nodes:
            self.index_node(tenant_id=tenant_id, node_id=str(node['id']))
        # Only discard superseded derived model versions after the full rebuild succeeds.
        with self.db.transaction():
            self.db.execute('DELETE FROM ago_semantic_vectors WHERE tenant_id=%s AND model_id<>%s',
                            (tenant_id, model.model_id))
        return {'indexed': len(nodes), 'model_id': model.model_id, 'complete': True}

    def upload(self, *, actor: Principal, filename: str, media_type: str,
               content: bytes, retention_days: int = 90) -> dict:
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if (not 1 <= len(filename.strip()) <= 250 or any(ord(c) < 32 for c in filename)
                or '/' in filename or '\\' in filename
                or media_type not in {'text/plain', 'application/pdf', 'application/octet-stream'}
                or type(retention_days) is not int or not 1 <= retention_days <= 365
                or not 1 <= len(content) <= MAX_BYTES):
            raise ValueError('Invalid private document')
        objects = self._bytes()
        identifier = str(uuid4())
        digest = hashlib.sha256(content).hexdigest()
        expires = datetime.now(timezone.utc) + timedelta(days=retention_days)
        installed = False
        try:
            with self.db.transaction():
                self.db.execute('SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE', (actor.tenant_id,))
                usage = self.db.execute(
                    """SELECT coalesce(sum(bytes),0) AS n,count(*) AS objects FROM ago_document_objects
                       WHERE tenant_id=%s AND status='active'""", (actor.tenant_id,)).fetchone()
                if usage['n'] + len(content) > MAX_TENANT_BYTES or usage['objects'] >= 2000:
                    raise ValueError('Private document quota reached')
                objects.write(actor.tenant_id, identifier, content)
                installed = True
                self.db.execute(
                    """INSERT INTO ago_document_objects
                       (id,tenant_id,author_id,filename,media_type,bytes,sha256,expires_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (identifier, actor.tenant_id, actor.subject, filename.strip(), media_type,
                     len(content), digest, expires))
        except Exception:
            if installed:
                objects.remove(actor.tenant_id, identifier)
            raise
        return {'id': identifier, 'sha256': digest, 'bytes': len(content),
                'expires_at': expires.isoformat(), 'source_ref': 'ago-object:' + identifier}

    def documents(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        UUID(tenant_id)
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Invalid object list limit')
        return [dict(row) for row in self.db.execute(
            """SELECT id,filename,media_type,bytes,sha256,created_at,expires_at
               FROM ago_document_objects WHERE tenant_id=%s AND status='active'
               AND expires_at>now() ORDER BY created_at DESC,id LIMIT %s""",
            (tenant_id, limit)).fetchall()]

    def download(self, *, tenant_id: str, object_id: str) -> tuple[dict, bytes]:
        UUID(tenant_id)
        UUID(object_id)
        row = self.db.execute(
            """SELECT id,filename,media_type,bytes,sha256 FROM ago_document_objects
               WHERE tenant_id=%s AND id=%s AND status='active' AND expires_at>now()""",
            (tenant_id, object_id)).fetchone()
        if not row:
            raise LookupError('Private document not found')
        return dict(row), self._bytes().read(tenant_id, object_id, row['sha256'], row['bytes'])

    def expire(self, *, tenant_id: str, limit: int = 100) -> dict:
        UUID(tenant_id)
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError('Invalid retention batch')
        objects = self._bytes()
        with self.db.transaction():
            rows = self.db.execute(
                """SELECT id,status FROM ago_document_objects WHERE tenant_id=%s
                   AND expires_at<=now() ORDER BY (status='active') DESC,expires_at,id
                   LIMIT %s FOR UPDATE""",
                (tenant_id, limit)).fetchall()
            for row in rows:
                if row['status'] == 'active':
                    self.db.execute(
                        """UPDATE ago_document_objects SET status='expired',expired_at=now()
                           WHERE tenant_id=%s AND id=%s""", (tenant_id, row['id']))
                objects.remove(tenant_id, str(row['id']))
        return {'processed': len(rows), 'tombstones_retained': True}

    def object_manifest(self, *, tenant_id: str) -> list[dict]:
        UUID(tenant_id)
        rows = self.db.execute(
            """SELECT id,bytes,sha256 FROM ago_document_objects
               WHERE tenant_id=%s AND status='active' ORDER BY id""", (tenant_id,)).fetchall()
        return [{'id': str(r['id']), 'bytes': r['bytes'], 'sha256': r['sha256']} for r in rows]

    def backup_objects(self, *, tenant_id: str, destination: str) -> dict:
        UUID(tenant_id)
        target = Path(destination).absolute()
        if target.exists() or target.parent.resolve() != target.parent:
            raise ValueError('Backup requires a new canonical directory')
        target.mkdir(mode=0o700)
        source = self._bytes()
        output = PrivateObjects(target)
        rows = self.object_manifest(tenant_id=tenant_id)
        for row in rows:
            output.write(tenant_id, row['id'], source.read(
                tenant_id, row['id'], row['sha256'], row['bytes']))
        manifest = {'format': 'ago-objects-v1', 'tenant_id': tenant_id, 'objects': rows}
        path = target / 'manifest.json'
        with path.open('x') as handle:
            path.chmod(0o600)
            json.dump(manifest, handle, sort_keys=True)
        return {'backed_up': len(rows), 'format': manifest['format']}

    def restore_objects(self, *, tenant_id: str, source: str, destination: str) -> dict:
        UUID(tenant_id)
        backup = PrivateObjects(source)
        manifest_file = backup.root / 'manifest.json'
        if manifest_file.is_symlink() or manifest_file.stat().st_size > 1024 * 1024:
            raise ValueError('Invalid object backup manifest')
        manifest = json.loads(manifest_file.read_text())
        expected = self.object_manifest(tenant_id=tenant_id)
        if (manifest != {'format': 'ago-objects-v1', 'tenant_id': tenant_id, 'objects': expected}):
            raise ValueError('Backup does not match restored database metadata')
        destination_path = Path(destination).absolute()
        if destination_path.exists() or destination_path.parent.resolve() != destination_path.parent:
            raise ValueError('Restore requires a new canonical directory')
        # Validate every object before creating even the isolated output directory.
        for row in expected:
            backup.read(tenant_id, row['id'], row['sha256'], row['bytes'])
        destination_path.mkdir(mode=0o700)
        output = PrivateObjects(destination_path)
        for row in expected:
            output.write(tenant_id, row['id'], backup.read(
                tenant_id, row['id'], row['sha256'], row['bytes']))
        return {'restored': len(expected), 'verified': True}
