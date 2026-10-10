"""M6 evidence-first organizational knowledge graph with independent human review.

Evidence review is not proof of factual truth or automatic policy activation.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.security import Principal
from ago.security_controls import SecurityControls


class KnowledgeStore:
    KINDS = frozenset(("fact", "policy", "artifact", "decision"))
    RELATIONS = frozenset(("supports", "contradicts", "depends_on", "references"))

    def __init__(self, db):
        self.db = db

    def propose(
        self, *, actor: Principal, kind: str, label: str,
        statement: str, source_ref: str,
    ) -> str:
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if kind not in self.KINDS:
            raise ValueError("Unsupported knowledge kind")
        if (not 1 <= len(label.strip()) <= 250
                or not 1 <= len(statement.strip()) <= 12000
                or not 1 <= len(source_ref.strip()) <= 1000):
            raise ValueError("Label, statement and evidence reference required")
        node_id = str(uuid4())
        with self.db.transaction():
            self.db.execute(
                """INSERT INTO ago_knowledge_nodes
                   (id,tenant_id,author_id,kind,label,statement,source_ref)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (node_id, actor.tenant_id, actor.subject, kind, label.strip(),
                 statement.strip(), source_ref.strip()),
            )
        return node_id

    def review(
        self, *, actor: Principal, node_id: str, approve: bool, note: str,
    ) -> dict:
        UUID(node_id)
        if not 1 <= len(note.strip()) <= 3000:
            raise ValueError("Independent review rationale required")
        with self.db.transaction():
            if not SecurityControls(self.db).permitted(
                actor, "knowledge:review", actor.tenant_id,
            ):
                raise PermissionError("Knowledge review permission required")
            reviewer = self.db.execute(
                """SELECT 1 FROM ago_users u JOIN ago_employees e
                     ON e.id=u.id AND e.tenant_id=u.tenant_id
                   WHERE u.tenant_id=%s AND u.id=%s
                     AND u.active=true AND e.kind='human'""",
                (actor.tenant_id, actor.subject),
            ).fetchone()
            if reviewer is None:
                raise PermissionError("Only an active human may review knowledge")
            node = self.db.execute(
                """SELECT author_id,status FROM ago_knowledge_nodes
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, node_id),
            ).fetchone()
            if node is None:
                raise LookupError("Knowledge node not found")
            if node["status"] != "pending" or str(node["author_id"]) == actor.subject:
                raise PermissionError("Independent pending knowledge review required")
            verdict = "verified" if approve else "rejected"
            self.db.execute(
                """UPDATE ago_knowledge_nodes SET status=%s,reviewer_id=%s,
                   review_note=%s,reviewed_at=now()
                   WHERE tenant_id=%s AND id=%s""",
                (verdict, actor.subject, note.strip(), actor.tenant_id, node_id),
            )
        return {"id": node_id, "status": verdict}

    def relate(
        self, *, actor: Principal, from_id: str, to_id: str, relation: str,
    ) -> str:
        for value in (actor.tenant_id, actor.subject, from_id, to_id):
            UUID(value)
        if from_id == to_id or relation not in self.RELATIONS:
            raise ValueError("Invalid evidence graph edge")
        with self.db.transaction():
            nodes = self.db.execute(
                """SELECT id,status FROM ago_knowledge_nodes
                   WHERE tenant_id=%s AND id IN (%s,%s)
                   ORDER BY id FOR SHARE""",
                (actor.tenant_id, from_id, to_id),
            ).fetchall()
            if len(nodes) != 2 or any(row["status"] != "verified" for row in nodes):
                raise PermissionError("Only reviewed same-tenant nodes may be linked")
            existing = self.db.execute(
                """SELECT id FROM ago_knowledge_edges
                   WHERE tenant_id=%s AND from_id=%s AND to_id=%s AND relation=%s""",
                (actor.tenant_id, from_id, to_id, relation),
            ).fetchone()
            if existing:
                return str(existing["id"])
            edge_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_knowledge_edges
                   (id,tenant_id,from_id,to_id,relation,author_id)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (edge_id, actor.tenant_id, from_id, to_id, relation, actor.subject),
            )
        return edge_id

    def verified(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 500:
            raise ValueError("Invalid search limit")
        return [dict(row) for row in self.db.execute(
            """SELECT id,kind,label,statement,source_ref,author_id,reviewer_id,
                      reviewed_at FROM ago_knowledge_nodes
               WHERE tenant_id=%s AND status='verified'
               ORDER BY reviewed_at DESC,id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()]

    def pending(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.db.execute(
            """SELECT id,kind,label,statement,source_ref,author_id,created_at
               FROM ago_knowledge_nodes WHERE tenant_id=%s AND status='pending'
               ORDER BY created_at,id LIMIT 200""",
            (tenant_id,),
        ).fetchall()]

    def edges(self, *, tenant_id: str, node_id: str) -> list[dict]:
        UUID(node_id)
        return [dict(row) for row in self.db.execute(
            """SELECT e.id,e.from_id,e.to_id,e.relation,e.created_at
               FROM ago_knowledge_edges e
               JOIN ago_knowledge_nodes source ON source.tenant_id=e.tenant_id
                 AND source.id=e.from_id AND source.status='verified'
               JOIN ago_knowledge_nodes target ON target.tenant_id=e.tenant_id
                 AND target.id=e.to_id AND target.status='verified'
               WHERE e.tenant_id=%s AND (e.from_id=%s OR e.to_id=%s)
               ORDER BY e.created_at,e.id LIMIT 500""",
            (tenant_id, node_id, node_id),
        ).fetchall()]
