"""Audited AI working-behavior measurements; no human psychometric or automatic HR scoring."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timezone
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.graph_store import instant
from ago.reviewed_changes import ReviewedChanges, canonical, digest
from ago.security import Principal
from ago.security_controls import SecurityControls

DIMENSIONS = (
    "trust",
    "reliability",
    "leadership",
    "collaboration",
    "communication",
    "decision_bias",
    "learning_velocity",
    "creativity",
    "risk_behavior",
    "mentoring",
    "conflict_resolution",
    "adaptability",
    "promotion_readiness",
)


def summarize_signals(samples, minimum=5):
    groups = {}
    for s in samples:
        key = (s["dimension"], s["scope"], s["complexity"], s["risk"])
        groups.setdefault(key, []).append(s)
    result = []
    for (dimension, scope, complexity, risk), rows in sorted(groups.items()):
        values = [float(x["score"]) for x in rows]
        n = len(values)
        mean = statistics.mean(values)
        se = statistics.stdev(values) / math.sqrt(n) if n > 1 else None
        enough = n >= minimum
        midpoint = n // 2
        delta = (
            statistics.mean(values[midpoint:]) - statistics.mean(values[:midpoint])
            if midpoint >= 2
            else None
        )
        result.append(
            {
                "dimension": dimension,
                "scope": scope,
                "complexity": complexity,
                "risk": risk,
                "n": n,
                "score": round(mean, 4) if enough else None,
                "insufficient_evidence": not enough,
                "interval_95": [
                    round(max(0, mean - 1.96 * se), 4),
                    round(min(1, mean + 1.96 * se), 4),
                ]
                if enough and se is not None
                else None,
                "drift_delta": round(delta, 4) if delta is not None else None,
                "method": "context-stratified unweighted mean; approximate interval, not population certification",
                "evidence_ids": [s["observation_id"] for s in rows],
            }
        )
    return result


class BehaviorStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _read(self, actor):
        sec = self.repositories.resolve(SecurityControls)
        if not (
            sec.permitted(actor, "organization:manage", actor.tenant_id)
            or sec.permitted(actor, "approval:decide", actor.tenant_id)
        ):
            raise PermissionError("Sensitive behavior review authority required")

    def _employee(self, actor, identifier):
        UUID(identifier)
        row = self.db.execute(
            "SELECT id,department_id,kind FROM ago_employees WHERE tenant_id=%s AND id=%s",
            (actor.tenant_id, identifier),
        ).fetchone()
        if not row or row["kind"] != "ai":
            raise PermissionError("Behavioral measurements are limited to same-tenant AI employees")
        return dict(row)

    def _rows(self, actor, employee_id=None):
        return [
            dict(r)
            for r in self.db.execute(
                """SELECT * FROM ago_behavior_records WHERE tenant_id=%s
            AND (%s::uuid IS NULL OR employee_id=%s) ORDER BY created_at,id LIMIT 2001""",
                (actor.tenant_id, employee_id, employee_id),
            ).fetchall()
        ]

    def _source(self, actor, command, spec):
        if command == "definition":
            return {}
        employee = self._employee(actor, spec["employee_id"])
        if command == "observation":
            row = self.db.execute(
                """SELECT t.id,t.action,t.status,t.assignee_id,t.created_at,t.updated_at,
                q.id qa_id,q.verdict,q.evidence,q.reviewer_id,q.created_at qa_at FROM ago_governed_tasks t
                JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
                WHERE t.tenant_id=%s AND t.id=%s AND t.assignee_id=%s AND t.status IN ('completed','failed')""",
                (actor.tenant_id, spec["task_id"], spec["employee_id"]),
            ).fetchone()
            if not row:
                raise PermissionError("Actual completed task with independent QA required")
            definition = self.db.execute(
                "SELECT payload FROM ago_behavior_records WHERE tenant_id=%s AND id=%s AND kind='definition'",
                (actor.tenant_id, spec["definition_id"]),
            ).fetchone()
            if not definition or definition["payload"]["dimension"] != spec["dimension"]:
                raise ValueError("Matching reviewed versioned metric definition required")
            return {"employee": employee, "task_qa": dict(row), "definition": definition["payload"]}
        return {
            "employee": employee,
            "profile": self.profile(actor=actor, employee_id=spec["employee_id"]),
        }

    def _validate(self, actor, command, spec):
        fields = {
            "definition": {
                "id",
                "dimension",
                "name",
                "rubric",
                "limitations",
                "minimum_samples",
                "version",
            },
            "observation": {
                "id",
                "employee_id",
                "definition_id",
                "task_id",
                "dimension",
                "scope",
                "complexity",
                "risk",
                "score",
                "rationale",
                "expires_at",
            },
            "decision": {"id", "employee_id", "scope", "action", "rationale", "expires_at"},
            "resolve_appeal": {
                "id",
                "employee_id",
                "appeal_id",
                "resolution",
                "excluded_observation_ids",
                "rationale",
            },
        }
        if command not in fields or not isinstance(spec, dict) or set(spec) != fields[command]:
            raise ValueError(
                "Strict behavioral schema required; personal/protected attributes are not accepted"
            )
        UUID(spec["id"])
        if command == "definition":
            if (
                spec["dimension"] not in DIMENSIONS
                or type(spec["version"]) is not int
                or spec["version"] < 1
                or type(spec["minimum_samples"]) is not int
                or not 5 <= spec["minimum_samples"] <= 100
            ):
                raise ValueError("Versioned dimension and minimum5 samples required")
            for field in ("name", "rubric", "limitations"):
                if not isinstance(spec[field], str) or not 1 <= len(spec[field]) <= 3000:
                    raise ValueError("Complete rubric required")
        else:
            self._employee(actor, spec["employee_id"])
            if not isinstance(spec["rationale"], str) or not 1 <= len(spec["rationale"]) <= 3000:
                raise ValueError("Evidence rationale required")
            if command != "resolve_appeal":
                expiry = instant(spec["expires_at"])
                now = datetime.now(timezone.utc)
                if not now < expiry or (expiry - now).days > 90:
                    raise ValueError("Behavior evidence expires within90 days")
                if not isinstance(spec["scope"], str) or not 1 <= len(spec["scope"]) <= 100:
                    raise ValueError("Domain scope required")
            if command == "observation":
                UUID(spec["task_id"])
                UUID(spec["definition_id"])
                if (
                    spec["dimension"] not in DIMENSIONS
                    or spec["complexity"] not in ("routine", "complex", "novel")
                    or spec["risk"] not in ("low", "medium", "high")
                ):
                    raise ValueError("Explicit dimension, task complexity and risk required")
                if type(spec["score"]) not in (int, float) or not 0 <= spec["score"] <= 1:
                    raise ValueError("Finite score0..1 required")
            if command == "decision" and spec["action"] not in (
                "assignment",
                "promotion",
                "autonomy",
                "learning",
                "hiring_gap",
            ):
                raise ValueError("Reviewable behavioral recommendation required")
            if command == "resolve_appeal":
                UUID(spec["appeal_id"])
                if (
                    spec["resolution"] not in ("upheld", "corrected")
                    or not isinstance(spec["excluded_observation_ids"], list)
                    or len(spec["excluded_observation_ids"]) > 100
                ):
                    raise ValueError("Appeal outcome and exact excluded sources required")
                appeal = self.db.execute(
                    "SELECT * FROM ago_behavior_appeals WHERE tenant_id=%s AND id=%s AND employee_id=%s",
                    (actor.tenant_id, spec["appeal_id"], spec["employee_id"]),
                ).fetchone()
                if (
                    not appeal
                    or self.db.execute(
                        "SELECT 1 FROM ago_behavior_records WHERE tenant_id=%s AND kind='resolve_appeal' AND payload->>'appeal_id'=%s",
                        (actor.tenant_id, spec["appeal_id"]),
                    ).fetchone()
                ):
                    raise ValueError("Open same-employee appeal required")
                for identifier in spec["excluded_observation_ids"]:
                    UUID(identifier)
                    if not self.db.execute(
                        "SELECT 1 FROM ago_behavior_records WHERE tenant_id=%s AND employee_id=%s AND id=%s AND kind='observation'",
                        (actor.tenant_id, spec["employee_id"], identifier),
                    ).fetchone():
                        raise PermissionError("Only same-employee observations may be corrected")

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
        ledger = self.repositories.resolve(ReviewedChanges)
        ledger.require(actor, "behavior")
        self._validate(actor, command, specification)
        return ledger.propose(
            actor=actor,
            domain="behavior",
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
            p = ledger.package(actor=actor, proposal_id=proposal_id, domain="behavior")
            if p.get("applied"):
                return p["applied"]
            spec = p["specification"]
            command = p["command"]
            self._validate(actor, command, spec)
            if digest(self._source(actor, command, spec)) != digest(p["source"]):
                raise PermissionError("Behavior evidence changed; review again")
            if command == "decision":
                profile = self.profile(actor=actor, employee_id=spec["employee_id"])
                if profile["open_appeals"] or not any(
                    x["scope"] == spec["scope"] and not x["insufficient_evidence"]
                    for x in profile["signals"]
                ):
                    raise PermissionError(
                        "Current sufficient scoped evidence and resolved appeals required"
                    )
            if (
                command == "observation"
                and self.db.execute(
                    "SELECT 1 FROM ago_behavior_records WHERE tenant_id=%s AND kind='observation' AND payload->>'task_id'=%s AND payload->>'dimension'=%s AND payload->>'definition_id'=%s",
                    (actor.tenant_id, spec["task_id"], spec["dimension"], spec["definition_id"]),
                ).fetchone()
            ):
                raise ValueError("Duplicate task/dimension observation")
            self.db.execute(
                """INSERT INTO ago_behavior_records(id,tenant_id,employee_id,kind,payload,source,proposal_id)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s)""",
                (
                    spec["id"],
                    actor.tenant_id,
                    spec.get("employee_id"),
                    command,
                    canonical(spec),
                    canonical(p["source"]),
                    p["id"],
                ),
            )
            return ledger.finish(
                actor=actor,
                package=p,
                result={"id": spec["id"], "kind": command, "advisory_only": True},
            )

    def profile(self, *, actor: Principal, employee_id: str) -> dict:
        self._read(actor)
        self._employee(actor, employee_id)
        rows = self._rows(actor, employee_id)
        if len(rows) > 2000:
            raise ValueError("Narrow behavioral history before aggregation")
        excluded = set()
        resolved = set()
        for r in rows:
            if r["kind"] == "resolve_appeal":
                excluded.update(r["payload"]["excluded_observation_ids"])
                resolved.add(r["payload"]["appeal_id"])
        appeals = [
            dict(x)
            for x in self.db.execute(
                "SELECT id,actor_id,reason,created_at FROM ago_behavior_appeals WHERE tenant_id=%s AND employee_id=%s ORDER BY created_at",
                (actor.tenant_id, employee_id),
            ).fetchall()
        ]
        now = datetime.now(timezone.utc)
        samples = []
        expired = []
        for r in rows:
            if r["kind"] != "observation" or str(r["id"]) in excluded:
                continue
            p = r["payload"]
            if instant(p["expires_at"]) <= now:
                expired.append(str(r["id"]))
                continue
            samples.append({**p, "observation_id": str(r["id"])})
        # Never mix different metric-definition versions into one score.
        signals = []
        for definition_id in sorted({s["definition_id"] for s in samples}):
            subset = [s for s in samples if s["definition_id"] == definition_id]
            definition = self.db.execute(
                "SELECT payload FROM ago_behavior_records WHERE tenant_id=%s AND id=%s AND kind='definition'",
                (actor.tenant_id, definition_id),
            ).fetchone()["payload"]
            signals.extend(
                {**x, "definition_id": definition_id, "definition_version": definition["version"]}
                for x in summarize_signals(subset, definition["minimum_samples"])
            )
        return {
            "employee_id": employee_id,
            "signals": signals,
            "observations": rows,
            "expired_ids": expired,
            "excluded_ids": sorted(excluded),
            "open_appeals": [a for a in appeals if str(a["id"]) not in resolved],
            "advisory_only": True,
            "missing_dimensions": sorted(set(DIMENSIONS) - {s["dimension"] for s in samples}),
            "validation": {
                "protected_attributes_used": False,
                "human_personality_inference": False,
                "context_stratified": True,
                "population_accuracy": "unvalidated until authentic prospective outcomes",
                "reviewed_observations": len(samples),
            },
        }

    def appeal(self, *, actor: Principal, employee_id: str, reason: str) -> dict:
        self._read(actor)
        self._employee(actor, employee_id)
        if not 1 <= len(reason.strip()) <= 3000:
            raise ValueError("Appeal reason required")
        identifier = str(uuid4())
        self.db.execute(
            "INSERT INTO ago_behavior_appeals(id,tenant_id,employee_id,actor_id,reason) VALUES(%s,%s,%s,%s,%s)",
            (identifier, actor.tenant_id, employee_id, actor.subject, reason),
        )
        return {"id": identifier, "status": "open", "high_impact_review_blocked": True}

    def require_clear(self, *, actor: Principal, employee_id: str) -> None:
        pending = self.db.execute(
            """SELECT 1 FROM ago_behavior_appeals a WHERE a.tenant_id=%s AND a.employee_id=%s
            AND NOT EXISTS(SELECT 1 FROM ago_behavior_records r WHERE r.tenant_id=a.tenant_id
                AND r.kind='resolve_appeal' AND r.payload->>'appeal_id'=a.id::text) LIMIT 1""",
            (actor.tenant_id, employee_id),
        ).fetchone()
        if pending:
            raise PermissionError(
                "Resolve behavioral appeal independently before high-impact personnel change"
            )
