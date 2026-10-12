"""Versioned enterprise graph. Every change is independently reviewed; reads recheck ACLs."""

from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid5, NAMESPACE_URL

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.reviewed_changes import ReviewedChanges, canonical, digest
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.semantic_memory_store import SemanticMemoryStore

NODE_KINDS = frozenset(
    "fact person employee department project workflow policy architecture research asset customer product incident skill model tool document memory audit decision".split()
)
RELATIONS = frozenset(
    "owns manages member_of depends_on governed_by produced_by approved_by references affects requires_skill has_skill uses_tool uses_model caused_by mitigated_by learned_from version_of simulates supports contradicts".split()
)
TYPED_RELATIONS = {
    "has_skill": ({"employee", "person", "department"}, {"skill"}),
    "requires_skill": ({"workflow", "project", "department", "employee"}, {"skill"}),
    "uses_tool": ({"workflow", "employee"}, {"tool"}),
    "uses_model": ({"workflow", "employee", "research"}, {"model"}),
    "member_of": ({"employee", "person"}, {"department"}),
    "governed_by": (NODE_KINDS, {"policy"}),
    "manages": ({"person", "employee"}, {"person", "employee", "department"}),
    "approved_by": (NODE_KINDS, {"person", "decision"}),
    "caused_by": ({"incident"}, NODE_KINDS),
}


def instant(value):
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if d.tzinfo is None:
            raise ValueError()
        return d.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ValueError("Timezone-aware ISO timestamp required") from exc


def node_spec(value):
    required = {
        "id",
        "kind",
        "label",
        "statement",
        "owner_id",
        "classification",
        "readers",
        "source_ref",
        "source_at",
        "confidence",
        "effective_at",
        "expires_at",
        "memory_ids",
        "legal_hold",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise ValueError("Complete typed graph provenance and retention required")
    UUID(value["id"])
    UUID(value["owner_id"])
    if value["kind"] not in NODE_KINDS or value["classification"] not in ("tenant", "restricted"):
        raise ValueError("Unknown node kind or classification")
    for field, maximum in [("label", 250), ("statement", 12000), ("source_ref", 1000)]:
        if not isinstance(value[field], str) or not 1 <= len(value[field].strip()) <= maximum:
            raise ValueError("Graph label, evidence and source required")
    for field in ("readers", "memory_ids"):
        if (
            not isinstance(value[field], list)
            or len(value[field]) > 50
            or len(set(value[field])) != len(value[field])
        ):
            raise ValueError("Bounded unique references required")
        for x in value[field]:
            UUID(x)
    if (
        type(value["confidence"]) not in (int, float)
        or not 0 <= value["confidence"] <= 1
        or type(value["legal_hold"]) is not bool
    ):
        raise ValueError("Explicit confidence and legal-hold state required")
    if not instant(value["source_at"]) <= datetime.now(timezone.utc) or not instant(
        value["effective_at"]
    ) < instant(value["expires_at"]):
        raise ValueError("Observed source and valid effective/expiry interval required")
    if (instant(value["expires_at"]) - instant(value["effective_at"])).days > 365:
        raise ValueError("Revalidation required within365 days")
    return value


class EnterpriseGraph:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _permission(self, actor):
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "knowledge:read", actor.tenant_id
        ):
            raise PermissionError("Knowledge read required")

    def _all(self, actor):
        rows = self.db.execute(
            """SELECT DISTINCT ON(entity_id) entity_id,entity_kind,revision,payload,created_at
            FROM ago_graph_versions WHERE tenant_id=%s ORDER BY entity_id,revision DESC LIMIT 5001""",
            (actor.tenant_id,),
        ).fetchall()
        if len(rows) > 5000:
            raise ValueError(
                "Graph snapshot exceeds bounded5000 entities; narrow data before querying"
            )
        return {str(r["entity_id"]): dict(r) for r in rows}

    def _visible(self, actor, node, now):
        p = node["payload"]
        if (
            node["entity_kind"] != "node"
            or p.get("deleted")
            or not instant(p["effective_at"]) <= now < instant(p["expires_at"])
        ):
            return False
        if p["classification"] != "tenant" and actor.subject not in [p["owner_id"], *p["readers"]]:
            return False
        if p.get("source_digest"):
            try:
                _, kind, identifier = p["source_ref"].split(":")
                if digest(self._record(actor, kind, identifier)) != p["source_digest"]:
                    return False
            except (ValueError, LookupError, PermissionError):
                return False
        for mid in p["memory_ids"]:
            try:
                self.repositories.resolve(SemanticMemoryStore).get(actor=actor, memory_id=mid)
            except (PermissionError, LookupError, ValueError):
                return False
        return True

    def _source(self, actor, command, spec):
        all_rows = self._all(actor)
        ids = [spec["id"]]
        if command == "edge":
            ids += [spec["from_id"], spec["to_id"]]
        if command == "merge":
            ids += [spec["target_id"]]
        source = {"entities": {x: digest(all_rows[x]) if x in all_rows else None for x in ids}}
        if command == "node" and spec["source_ref"].startswith("ago:"):
            parts = spec["source_ref"].split(":")
            if len(parts) != 3 or parts[1] != spec["kind"]:
                raise ValueError("Exact typed source reference required")
            source["record"] = self._record(actor, parts[1], parts[2])
        return source

    def _validate(self, actor, command, spec):
        rows = self._all(actor)
        now = datetime.now(timezone.utc)
        if command == "node":
            node_spec(spec)
            for uid in [spec["owner_id"], *spec["readers"]]:
                if not self.db.execute(
                    "SELECT 1 FROM ago_users WHERE tenant_id=%s AND id=%s AND active",
                    (actor.tenant_id, uid),
                ).fetchone():
                    raise PermissionError("Same-tenant active graph owner/readers required")
            for mid in spec["memory_ids"]:
                m = self.repositories.resolve(SemanticMemoryStore).get(actor=actor, memory_id=mid)
                if m["scope"] != "company" or spec["classification"] != "tenant":
                    raise PermissionError(
                        "Graph synchronization accepts company memory only; private memories stay private"
                    )
            if spec["id"] in rows and rows[spec["id"]]["entity_kind"] != "node":
                raise ValueError("Entity type immutable")
        elif command == "edge":
            if set(spec) != {
                "id",
                "from_id",
                "to_id",
                "relation",
                "source_ref",
                "confidence",
                "inferred",
                "expires_at",
            }:
                raise ValueError("Complete relationship provenance required")
            for k in ("id", "from_id", "to_id"):
                UUID(spec[k])
            if spec["from_id"] == spec["to_id"] or spec["relation"] not in RELATIONS:
                raise ValueError("Invalid relationship")
            ends = [rows.get(spec[k]) for k in ("from_id", "to_id")]
            if any(not n or not self._visible(actor, n, now) for n in ends):
                raise PermissionError("Current accessible endpoints required")
            if (
                type(spec["confidence"]) not in (int, float)
                or not 0 <= spec["confidence"] <= 1
                or type(spec["inferred"]) is not bool
            ):
                raise ValueError("Explicit relationship confidence and inference required")
            if (
                not isinstance(spec["source_ref"], str)
                or not 1 <= len(spec["source_ref"]) <= 1000
                or instant(spec["expires_at"]) <= now
            ):
                raise ValueError("Current source and revalidation required")
            types = TYPED_RELATIONS.get(spec["relation"])
            if types and any(n["payload"]["kind"] not in t for n, t in zip(ends, types)):
                raise ValueError("Relation endpoint types do not match schema")
            if spec["id"] in rows and rows[spec["id"]]["entity_kind"] != "edge":
                raise ValueError("Entity type immutable")
        elif command in ("delete", "merge"):
            expected = {"id", "reason"} | ({"target_id"} if command == "merge" else set())
            if (
                set(spec) != expected
                or not isinstance(spec["reason"], str)
                or not 1 <= len(spec["reason"]) <= 3000
            ):
                raise ValueError("Explicit lifecycle reason required")
            old = rows.get(spec["id"])
            if not old or old["payload"].get("deleted"):
                raise LookupError("Current graph entity required")
            if old["payload"].get("legal_hold"):
                raise PermissionError("Legal hold prevents deletion or merging")
            if command == "merge":
                target = rows.get(spec["target_id"])
                if (
                    old["entity_kind"] != "node"
                    or not target
                    or not self._visible(actor, target, now)
                    or old["payload"]["kind"] != target["payload"]["kind"]
                    or spec["id"] == spec["target_id"]
                ):
                    raise ValueError("Distinct visible duplicate of same kind required")
                if (
                    old["payload"]["classification"] != target["payload"]["classification"]
                    or set(old["payload"]["readers"]) != set(target["payload"]["readers"])
                    or old["payload"]["owner_id"] != target["payload"]["owner_id"]
                ):
                    raise PermissionError("Merging cannot widen classification or audience")
        else:
            raise ValueError("Unknown graph command")

    def propose(
        self,
        *,
        actor: Principal,
        command: str,
        specification: dict,
        operation_key: str,
        base_revision: int,
        rationale: str,
    ) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "graph")
        self._validate(actor, command, specification)
        return self.repositories.resolve(ReviewedChanges).propose(
            actor=actor,
            domain="graph",
            command=command,
            specification=specification,
            source=self._source(actor, command, specification),
            operation_key=operation_key,
            base_revision=base_revision,
            rationale=rationale,
        )

    def apply(self, *, actor: Principal, proposal_id: str) -> dict:
        ledger = self.repositories.resolve(ReviewedChanges)
        with self.db.transaction():
            p = ledger.package(actor=actor, proposal_id=proposal_id, domain="graph")
            if p.get("applied"):
                return p["applied"]
            spec = p["specification"]
            command = p["command"]
            self._validate(actor, command, spec)
            if self._source(actor, command, spec) != p["source"]:
                raise PermissionError("Graph source changed since review")
            rows = self._all(actor)
            changes = []
            if command in ("node", "edge"):
                changes = [(spec["id"], command, spec)]
            else:
                old = rows[spec["id"]]
                changes = [
                    (
                        spec["id"],
                        old["entity_kind"],
                        {
                            **old["payload"],
                            "deleted": True,
                            "reason": spec["reason"],
                            "merged_into": spec.get("target_id"),
                        },
                    )
                ]
                for key, r in rows.items():
                    payload = r["payload"]
                    if (
                        r["entity_kind"] == "edge"
                        and not payload.get("deleted")
                        and spec["id"] in (payload["from_id"], payload["to_id"])
                    ):
                        replacement = {**payload}
                        if command == "merge":
                            for field in ("from_id", "to_id"):
                                if replacement[field] == spec["id"]:
                                    replacement[field] = spec["target_id"]
                            replacement["deleted"] = replacement["from_id"] == replacement["to_id"]
                        else:
                            replacement["deleted"] = True
                        changes.append((key, "edge", replacement))
            for identifier, kind, payload in changes:
                if command == "node" and "record" in p["source"]:
                    payload = {**payload, "source_digest": digest(p["source"]["record"])}
                self.db.execute(
                    """INSERT INTO ago_graph_versions(tenant_id,entity_id,entity_kind,revision,payload,proposal_id)
                    VALUES(%s,%s,%s,%s,%s::jsonb,%s)""",
                    (
                        actor.tenant_id,
                        identifier,
                        kind,
                        p["base_revision"] + 1,
                        canonical(payload),
                        p["id"],
                    ),
                )
                if kind == "node":
                    for mid in payload["memory_ids"]:
                        self.db.execute(
                            "DELETE FROM ago_memory_vectors WHERE tenant_id=%s AND memory_id=%s",
                            (actor.tenant_id, mid),
                        )
                        self.db.execute(
                            """INSERT INTO ago_graph_reindex(tenant_id,memory_id,graph_id,revision)
                            VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
                            (actor.tenant_id, mid, identifier, p["base_revision"] + 1),
                        )
            return ledger.finish(
                actor=actor,
                package=p,
                result={"entities": [x[0] for x in changes], "memory_reindex_required": True},
            )

    def query(
        self,
        *,
        actor: Principal,
        root_id: str | None = None,
        relation: str | None = None,
        kind: str | None = None,
        direction: str = "both",
        depth: int = 2,
        limit: int = 100,
    ) -> dict:
        self._permission(actor)
        if (
            type(depth) is not int
            or not 0 <= depth <= 6
            or not 1 <= limit <= 500
            or direction not in ("both", "out", "in")
        ):
            raise ValueError("Bounded graph traversal required")
        if (
            relation is not None
            and relation not in RELATIONS
            or kind is not None
            and kind not in NODE_KINDS
        ):
            raise ValueError("Unknown graph filter")
        rows = self._all(actor)
        now = datetime.now(timezone.utc)
        nodes = {k: v for k, v in rows.items() if self._visible(actor, v, now)}
        edges = [
            v
            for v in rows.values()
            if v["entity_kind"] == "edge"
            and not v["payload"].get("deleted")
            and instant(v["payload"]["expires_at"]) > now
            and v["payload"]["from_id"] in nodes
            and v["payload"]["to_id"] in nodes
            and (relation is None or v["payload"]["relation"] == relation)
        ]
        paths = {}
        if root_id:
            if root_id not in nodes:
                raise LookupError("Visible graph root not found")
            paths = {root_id: [root_id]}
            queue = deque([(root_id, 0)])
            while queue and len(paths) <= limit:
                current, d = queue.popleft()
                if d >= depth:
                    continue
                for edge in edges:
                    p = edge["payload"]
                    target = None
                    if direction in ("out", "both") and p["from_id"] == current:
                        target = p["to_id"]
                    if direction in ("in", "both") and p["to_id"] == current:
                        target = p["from_id"]
                    if target and target not in paths:
                        paths[target] = paths[current] + [target]
                        queue.append((target, d + 1))
                        if len(paths) > limit:
                            break
            selected = [k for k in paths if kind is None or nodes[k]["payload"]["kind"] == kind]
        else:
            selected = [k for k in nodes if kind is None or nodes[k]["payload"]["kind"] == kind]
        truncated = len(selected) > limit
        selected = selected[:limit]
        keys = set(selected)
        output_edges = [
            e for e in edges if e["payload"]["from_id"] in keys and e["payload"]["to_id"] in keys
        ]
        return {
            "revision": self.repositories.resolve(ReviewedChanges).revision(
                tenant_id=actor.tenant_id, domain="graph"
            ),
            "nodes": [nodes[k] for k in selected],
            "edges": output_edges[:500],
            "paths": {k: paths[k] for k in selected if k in paths},
            "truncated": truncated or len(output_edges) > 500,
            "schema": {"node_types": sorted(NODE_KINDS), "relations": sorted(RELATIONS)},
        }

    def quality(self, *, actor: Principal) -> dict:
        result = self.query(actor=actor, limit=500)
        nodes = result["nodes"]
        edges = result["edges"]
        degrees = {str(n["entity_id"]): 0 for n in nodes}
        contradictions = []
        for e in edges:
            p = e["payload"]
            degrees[p["from_id"]] += 1
            degrees[p["to_id"]] += 1
            if p["relation"] == "contradicts":
                contradictions.append(str(e["entity_id"]))
        return {
            "revision": result["revision"],
            "visible_nodes": len(nodes),
            "visible_edges": len(edges),
            "orphan_ids": [k for k, v in degrees.items() if v == 0],
            "centrality_risks": [k for k, v in degrees.items() if v >= 10],
            "low_confidence": [
                str(n["entity_id"]) for n in nodes if n["payload"]["confidence"] < 0.5
            ],
            "contradictions": contradictions,
            "truncated": result["truncated"],
            "interpretation": "Observed visible graph indicators; inferred causal links are not causal proof",
        }

    def synchronize(self, *, actor: Principal, limit: int = 20) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "graph")
        if not 1 <= limit <= 50:
            raise ValueError("Invalid reindex batch")
        done = []
        unavailable = []
        rows = self.db.execute(
            "SELECT * FROM ago_graph_reindex WHERE tenant_id=%s AND completed_at IS NULL ORDER BY revision,memory_id LIMIT %s",
            (actor.tenant_id, limit),
        ).fetchall()
        for r in rows:
            try:
                self.repositories.resolve(SemanticMemoryStore).index(
                    actor=actor, memory_id=str(r["memory_id"])
                )
            except (ValueError, PermissionError, LookupError):
                unavailable.append(str(r["memory_id"]))
                continue
            self.db.execute(
                "UPDATE ago_graph_reindex SET completed_at=clock_timestamp() WHERE tenant_id=%s AND memory_id=%s AND graph_id=%s AND revision=%s",
                (actor.tenant_id, r["memory_id"], r["graph_id"], r["revision"]),
            )
            done.append(str(r["memory_id"]))
        return {"indexed": done, "unavailable": unavailable}

    def _record(self, actor, kind, identifier):
        tables = {
            "employee": ("ago_employees", "id,name,kind,department_id,manager_id"),
            "department": ("ago_departments", "id,name"),
            "project": ("ago_goals", "id,title,status,description"),
            "workflow": ("ago_governed_tasks", "id,action,status,assignee_id"),
        }
        if kind not in tables:
            raise ValueError("Supported source: employee, department, project or workflow")
        UUID(identifier)
        table, fields = tables[kind]
        row = self.db.execute(
            f"SELECT {fields} FROM {table} WHERE tenant_id=%s AND id=%s",
            (actor.tenant_id, identifier),
        ).fetchone()
        if not row:
            raise LookupError("Same-tenant source record required")
        import json

        return json.loads(canonical(dict(row)))

    def source(self, *, actor: Principal, kind: str, identifier: str) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "graph")
        record = self._record(actor, kind, identifier)
        now = datetime.now(timezone.utc)
        ref = "ago:" + kind + ":" + identifier
        return {
            "id": str(uuid5(NAMESPACE_URL, actor.tenant_id + ":" + ref)),
            "kind": kind,
            "label": record.get("name", record.get("title", record.get("action", kind))),
            "statement": canonical(record),
            "owner_id": actor.subject,
            "classification": "restricted",
            "readers": [],
            "source_ref": ref,
            "source_at": now.isoformat(),
            "confidence": 1.0,
            "effective_at": now.isoformat(),
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "memory_ids": [],
            "legal_hold": False,
        }
