"""Scope-first experience memory; content/vector deletion and provenance auditing."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.memory_policies import extractive_summary, validate_memory
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.storage_adapters import StorageUnavailable, normalized, offline_encoder


class SemanticMemoryStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None,
                 encoder=None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)
        self.encoder = encoder

    def _permission(self, actor, permission):
        if not self.repositories.resolve(SecurityControls).permitted(actor, permission, actor.tenant_id):
            raise PermissionError('Memory permission required')

    def _audit(self, actor, action, identifier, metadata=None):
        self.repositories.resolve(SecurityControls).audit(action, 'accepted', tenant_id=actor.tenant_id,
            actor_id=actor.subject, metadata={'memory_id': identifier, **(metadata or {})})

    def _model(self):
        return self.encoder or offline_encoder()

    def _lock(self, actor):
        # Serializes mutations, consolidation and index updates for this tenant.
        self.db.execute('SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE', (actor.tenant_id,))

    def _scope(self, actor, scope, identifier):
        if scope == 'employee':
            valid = identifier == actor.subject
        elif scope == 'company':
            valid = identifier == actor.tenant_id
        elif scope == 'department':
            valid = self.db.execute('SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND department_id=%s',
                                    (actor.tenant_id, actor.subject, identifier)).fetchone()
        elif scope == 'project':
            valid = self.db.execute('SELECT 1 FROM ago_memory_projects WHERE tenant_id=%s AND goal_id=%s AND user_id=%s',
                                    (actor.tenant_id, identifier, actor.subject)).fetchone()
        else:
            valid = False
        if not valid:
            raise PermissionError('Memory scope membership required')

    def _rows(self, actor, identifier=None):
        rows = self.db.execute(
            """SELECT m.* FROM ago_scoped_memories m
               WHERE m.tenant_id=%s AND m.state='active' AND m.expires_at>clock_timestamp()
                 AND (%s::uuid IS NULL OR m.id=%s)
                 AND (m.scope='company' OR (m.scope='employee' AND m.owner_id=%s)
                  OR (m.scope='department' AND EXISTS(SELECT 1 FROM ago_employees e
                      WHERE e.tenant_id=m.tenant_id AND e.id=%s AND e.department_id=m.department_id))
                  OR (m.scope='project' AND EXISTS(SELECT 1 FROM ago_memory_projects p
                      WHERE p.tenant_id=m.tenant_id AND p.goal_id=m.goal_id AND p.user_id=%s)))
               ORDER BY m.created_at,m.id LIMIT 2001""",
            (actor.tenant_id, identifier, identifier, actor.subject, actor.subject, actor.subject)).fetchall()
        if len(rows) > 2000:
            raise StorageUnavailable('Memory retrieval requires bounded archival')
        return [dict(row) for row in rows]

    def create(self, *, actor: Principal, scope: str, scope_id: str, kind: str,
               content: str, source_ref: str, retention_hours: int = 2160,
               knowledge_id: str | None = None) -> dict:
        validate_memory(scope, scope_id, kind, content, source_ref, retention_hours)
        if knowledge_id:
            UUID(knowledge_id)
        with self.db.transaction():
            self._permission(actor, 'memory:write')
            self._lock(actor)
            self._scope(actor, scope, scope_id)
            count = self.db.execute("SELECT count(*) AS count FROM ago_scoped_memories WHERE tenant_id=%s AND state='active'",
                                    (actor.tenant_id,)).fetchone()['count']
            if count >= 2000:
                raise ValueError('Memory quota exceeded; expire or forget records')
            if knowledge_id and not self.db.execute(
                "SELECT 1 FROM ago_knowledge_nodes WHERE tenant_id=%s AND id=%s AND status='verified'",
                (actor.tenant_id, knowledge_id)).fetchone():
                raise PermissionError('Same-tenant verified evidence required')
            identifier = str(uuid4())
            row = self.db.execute(
                """INSERT INTO ago_scoped_memories(id,tenant_id,owner_id,scope,scope_id,kind,content,
                   source_ref,knowledge_id,department_id,goal_id,employee_id,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now()+(%s*interval '1 hour')) RETURNING *""",
                (identifier, actor.tenant_id, actor.subject, scope, scope_id, kind, content.strip(),
                 source_ref.strip(), knowledge_id, scope_id if scope == 'department' else None,
                 scope_id if scope == 'project' else None, scope_id if scope == 'employee' else None,
                 retention_hours)).fetchone()
            self._audit(actor, 'memory.create', identifier, {'scope': scope, 'kind': kind,
                        'content_sha256': hashlib.sha256(content.strip().encode()).hexdigest(),
                        'knowledge_id': knowledge_id})
        return dict(row)

    def get(self, *, actor: Principal, memory_id: str) -> dict:
        UUID(memory_id)
        self._permission(actor, 'memory:read')
        records = self._rows(actor, memory_id)
        if not records:
            raise LookupError('Accessible memory not found')
        row = records[0]
        row['sources'] = [dict(r) for r in self.db.execute(
            'SELECT source_id,source_revision FROM ago_memory_sources WHERE tenant_id=%s AND memory_id=%s ORDER BY source_id',
            (actor.tenant_id, memory_id)).fetchall()]
        return row

    def index(self, *, actor: Principal, memory_id: str) -> dict:
        with self.db.transaction():
            self._permission(actor, 'memory:write')
            self._lock(actor)
            record = self.get(actor=actor, memory_id=memory_id)
            model = self._model()
            vector = normalized(model.embed(record['content']))
            self.db.execute(
                """INSERT INTO ago_memory_vectors(tenant_id,memory_id,revision,model_id,vector)
                   VALUES(%s,%s,%s,%s,%s::jsonb) ON CONFLICT(tenant_id,memory_id)
                   DO UPDATE SET revision=excluded.revision,model_id=excluded.model_id,vector=excluded.vector""",
                (actor.tenant_id, memory_id, record['revision'], model.model_id, json.dumps(vector)))
            self._audit(actor, 'memory.index', memory_id, {'revision': record['revision'], 'model_id': model.model_id})
        return {'id': memory_id, 'revision': record['revision'], 'model_id': model.model_id}

    def search(self, *, actor: Principal, query: str, limit: int = 10) -> dict:
        self._permission(actor, 'memory:read')
        if not 1 <= len(query.strip()) <= 1000 or type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError('Invalid bounded memory query')
        with self.db.transaction():
            self._lock(actor)
            records = self._rows(actor)
            model = self._model()
            needle = normalized(model.embed(query, query=True))
            vectors = {str(row['memory_id']): dict(row) for row in self.db.execute(
                'SELECT memory_id,revision,vector FROM ago_memory_vectors WHERE tenant_id=%s AND model_id=%s',
                (actor.tenant_id, model.model_id)).fetchall()}
            results = []
            for record in records:
                indexed = vectors.get(str(record['id']))
                if indexed and indexed['revision'] == record['revision']:
                    vector = normalized(indexed['vector'])
                    results.append({**record, 'score': sum(a*b for a,b in zip(needle, vector))})
            results.sort(key=lambda row: (-row['score'], str(row['id'])))
        return {'model_id': model.model_id, 'indexed': len(results), 'results': results[:limit]}

    def consolidate(self, *, actor: Principal, memory_ids: list[str]) -> dict:
        if not 2 <= len(memory_ids) <= 20 or len(set(memory_ids)) != len(memory_ids):
            raise ValueError('Distinct consolidation sources required')
        with self.db.transaction():
            self._permission(actor, 'memory:write')
            self._lock(actor)
            records = [self.get(actor=actor, memory_id=identifier) for identifier in memory_ids]
            if len({(r['scope'], r['scope_id']) for r in records}) != 1:
                raise PermissionError('Consolidation cannot widen memory scope')
            if any(r['kind'] == 'summary' for r in records):
                raise ValueError('Consolidate original experiences, not derived summaries')
            first = records[0]
            hours = int((min(r['expires_at'] for r in records) - datetime.now(timezone.utc)).total_seconds() // 3600)
            if hours < 1:
                raise ValueError('Sources expire too soon for consolidation')
            summary = self.create(actor=actor, scope=first['scope'], scope_id=str(first['scope_id']),
                kind='summary', content=extractive_summary(records), source_ref='internal:memory:consolidation',
                retention_hours=hours)
            for record in records:
                self.db.execute('INSERT INTO ago_memory_sources(tenant_id,memory_id,source_id,source_revision) VALUES(%s,%s,%s,%s)',
                    (actor.tenant_id, summary['id'], record['id'], record['revision']))
            self._audit(actor, 'memory.consolidate', str(summary['id']), {'source_ids': memory_ids})
        return self.get(actor=actor, memory_id=str(summary['id']))

    def _scrub(self, actor, identifiers, state):
        self.db.execute('DELETE FROM ago_memory_vectors WHERE tenant_id=%s AND memory_id=ANY(%s::uuid[])',
                        (actor.tenant_id, identifiers))
        self.db.execute("UPDATE ago_scoped_memories SET state=%s,content=NULL,source_ref='redacted',knowledge_id=NULL WHERE tenant_id=%s AND id=ANY(%s::uuid[])",
                        (state, actor.tenant_id, identifiers))

    def _derived(self, actor, identifier):
        return [str(r['memory_id']) for r in self.db.execute(
            'SELECT memory_id FROM ago_memory_sources WHERE tenant_id=%s AND source_id=%s',
            (actor.tenant_id, identifier)).fetchall()]

    def correct(self, *, actor: Principal, memory_id: str, content: str,
                expected_revision: int, reason: str) -> dict:
        if type(expected_revision) is not int or not 1 <= len(reason.strip()) <= 500 or not 1 <= len(content.strip()) <= 12000:
            raise ValueError('Correction content, revision and rationale required')
        with self.db.transaction():
            self._permission(actor, 'memory:write')
            self._lock(actor)
            record = self.get(actor=actor, memory_id=memory_id)
            if str(record['owner_id']) != actor.subject or record['kind'] == 'summary':
                raise PermissionError('Only original owner can correct experience')
            if record['revision'] != expected_revision:
                raise ValueError('Memory revision conflict')
            self._scrub(actor, self._derived(actor, memory_id), 'superseded')
            self.db.execute('DELETE FROM ago_memory_vectors WHERE tenant_id=%s AND memory_id=%s', (actor.tenant_id, memory_id))
            self.db.execute('UPDATE ago_scoped_memories SET content=%s,revision=revision+1 WHERE tenant_id=%s AND id=%s',
                            (content.strip(), actor.tenant_id, memory_id))
            self._audit(actor, 'memory.correct', memory_id, {'previous_revision': expected_revision,
                'reason': reason.strip(), 'content_sha256': hashlib.sha256(content.strip().encode()).hexdigest()})
        return self.get(actor=actor, memory_id=memory_id)

    def forget(self, *, actor: Principal, memory_id: str, reason: str) -> dict:
        if not 1 <= len(reason.strip()) <= 500:
            raise ValueError('Forgetting rationale required')
        with self.db.transaction():
            self._permission(actor, 'memory:write')
            self._lock(actor)
            record = self.get(actor=actor, memory_id=memory_id)
            if str(record['owner_id']) != actor.subject:
                raise PermissionError('Only owner can forget accessible memory')
            identifiers = [memory_id, *self._derived(actor, memory_id)]
            self._scrub(actor, identifiers, 'forgotten')
            self._audit(actor, 'memory.forget', memory_id, {'reason': reason.strip(), 'scrubbed': len(identifiers)})
        return {'id': memory_id, 'state': 'forgotten', 'scrubbed': len(identifiers)}

    def expire(self, *, actor: Principal, limit: int = 100) -> dict:
        if type(limit) is not int or not 1 <= limit <= 200:
            raise ValueError('Invalid memory cleanup limit')
        with self.db.transaction():
            self._permission(actor, 'memory:manage')
            self._lock(actor)
            expired = self.db.execute("SELECT id FROM ago_scoped_memories WHERE tenant_id=%s AND state='active' AND expires_at<=clock_timestamp() ORDER BY expires_at LIMIT %s",
                                      (actor.tenant_id, limit)).fetchall()
            identifiers = set()
            for row in expired:
                identifier = str(row['id'])
                identifiers.update([identifier, *self._derived(actor, identifier)])
            self._scrub(actor, list(identifiers), 'forgotten')
            self._audit(actor, 'memory.expire', None, {'scrubbed': len(identifiers)})
        return {'scrubbed': len(identifiers)}

    def set_project_member(self, *, actor: Principal, goal_id: str, user_id: str, member: bool) -> dict:
        UUID(goal_id)
        UUID(user_id)
        if type(member) is not bool:
            raise ValueError('Strict membership decision required')
        with self.db.transaction():
            self._permission(actor, 'memory:manage')
            self._lock(actor)
            human = self.db.execute("SELECT 1 FROM ago_employees WHERE tenant_id=%s AND id=%s AND kind='human'",
                                    (actor.tenant_id, actor.subject)).fetchone()
            goal = self.db.execute('SELECT 1 FROM ago_goals WHERE tenant_id=%s AND id=%s', (actor.tenant_id, goal_id)).fetchone()
            user = self.db.execute('SELECT 1 FROM ago_users WHERE tenant_id=%s AND id=%s AND active=true', (actor.tenant_id, user_id)).fetchone()
            if not human or not goal or not user:
                raise PermissionError('Human operator and same-tenant goal/user required')
            if member:
                self.db.execute('INSERT INTO ago_memory_projects(tenant_id,goal_id,user_id) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',
                                (actor.tenant_id, goal_id, user_id))
            else:
                self.db.execute('DELETE FROM ago_memory_projects WHERE tenant_id=%s AND goal_id=%s AND user_id=%s',
                                (actor.tenant_id, goal_id, user_id))
            self._audit(actor, 'memory.membership', None, {'goal_id': goal_id, 'user_id': user_id, 'member': member})
        return {'goal_id': goal_id, 'user_id': user_id, 'member': member}
