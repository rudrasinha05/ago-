"""PostgreSQL application adapter for bounded Sections 21-27 operations.

All writes require signed-session actor at the API boundary. High-impact actions
also require independently decided, exact-action governance approvals. This is
local/tenant-scoped software, not a financial settlement or autonomous authority.
"""
from __future__ import annotations

import base64
import binascii
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.enterprise_domains import (
    ASSET_TYPES, AssetIdentity, HORIZONS, OperatingMode, WorkCandidate,
    WorkerState, agent_evidence_intent, allocate, evaluate_change, operational_load, organization_change_intent,
    transition_mode, transition_worker, twin_scenario, validate_horizon,
)
from ago.security import Principal


class EnterpriseOperationsStore:
    def __init__(self, connection: DatabaseConnection, *,
                 repositories: RepositoryScope | None = None):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def _tenant_lock(self, tenant_id: str) -> None:
        if not self.connection.execute(
            "SELECT 1 FROM ago_tenants WHERE id=%s FOR UPDATE",
            (str(UUID(tenant_id)),)
        ).fetchone():
            raise LookupError("Organization not found")

    def _approval(self, actor: Principal, approval_id: str, action: str) -> None:
        row = self.connection.execute(
            """SELECT requester_id, reviewer_id, status, action
               FROM ago_approval_requests WHERE tenant_id=%s AND id=%s""",
            (actor.tenant_id, str(UUID(approval_id)))
        ).fetchone()
        if not row or row["status"] != "approved" or row["action"] != action:
            raise PermissionError("Independent exact-action approval required")
        if str(row["requester_id"]) != actor.subject or (
            not row["reviewer_id"] or str(row["reviewer_id"]) == actor.subject
        ):
            raise PermissionError("No self approval or delegated requester substitution")

    def modes(self, *, tenant_id: str, scope_kind: str = "company",
              scope_id: str | None = None) -> list[dict]:
        if scope_kind not in ("company", "department", "employee") or (
            (scope_kind == "company") != (scope_id is None)
        ):
            raise ValueError("Invalid mode scope")
        if scope_id:
            UUID(scope_id)
        rows = self.connection.execute(
            """SELECT id,mode,sequence,scope_kind,scope_id,actor_id,rationale,
                      approval_id,expires_at,created_at
               FROM ago_oos_mode_events
               WHERE tenant_id=%s AND scope_kind=%s
                  AND scope_id IS NOT DISTINCT FROM %s::uuid
               ORDER BY sequence DESC LIMIT 100""",
            (str(UUID(tenant_id)), scope_kind, scope_id),
        ).fetchall()
        return [dict(x) for x in rows]

    def mode_change(self, *, actor: Principal, target: str,
                    approval_id: str, reason: str, expires_at: datetime,
                    scope_kind: str = "company", scope_id: str | None = None) -> dict:
        tenant = str(UUID(actor.tenant_id))
        target_mode = OperatingMode(target)
        if scope_kind not in ("company", "department", "employee") or (
            (scope_kind == "company") != (scope_id is None)
        ):
            raise ValueError("Invalid operating scope")
        if not reason.strip() or len(reason) > 3000:
            raise ValueError("Bounded rationale required")
        if expires_at.tzinfo is None:
            raise ValueError("Timezone-aware expiry required")
        now = datetime.now(timezone.utc)
        if not now < expires_at <= now + timedelta(days=7):
            raise ValueError("Mode must expire within seven days")
        scope = str(UUID(scope_id)) if scope_id else None
        action = "enterprise:mode:" + scope_kind + ":" + (scope or "company") + ":" + target
        with self.connection.transaction():
            self._tenant_lock(tenant)
            if scope:
                table = "ago_departments" if scope_kind == "department" else "ago_employees"
                if not self.connection.execute(
                    f"SELECT 1 FROM {table} WHERE tenant_id=%s AND id=%s",
                    (tenant, scope),
                ).fetchone():
                    raise LookupError("Operating scope missing")
            previous = self.connection.execute(
                """SELECT id,mode,sequence FROM ago_oos_mode_events
                   WHERE tenant_id=%s AND scope_kind=%s
                   AND scope_id IS NOT DISTINCT FROM %s::uuid
                   ORDER BY sequence DESC LIMIT 1""",
                (tenant, scope_kind, scope),
            ).fetchone()
            already = self.connection.execute(
                """SELECT id,mode,sequence,scope_kind,scope_id,rationale,expires_at
                   FROM ago_oos_mode_events
                   WHERE tenant_id=%s AND approval_id=%s""",
                (tenant, str(UUID(approval_id)))
            ).fetchone()
            if already:
                if (already["mode"] != target_mode.value or already["scope_kind"] != scope_kind
                    or (str(already["scope_id"]) if already["scope_id"] else None) != scope
                    or already["rationale"] != reason.strip()
                    or already["expires_at"] != expires_at):
                    raise PermissionError("Approval already used for a different operating action")
                return {"id": str(already["id"]), "mode": already["mode"],
                        "sequence": already["sequence"],
                        "expires_at": already["expires_at"], "idempotent": True}
            self._approval(actor, approval_id, action)
            previous_mode = OperatingMode(previous["mode"]) if previous else OperatingMode.ACTIVE
            transition_mode(previous_mode, target_mode, approved=True, reason=reason)
            identifier = str(uuid4())
            sequence = int(previous["sequence"]) + 1 if previous else 1
            self.connection.execute(
                """INSERT INTO ago_oos_mode_events
                (id,tenant_id,scope_kind,scope_id,mode,sequence,
                 actor_id,approval_id,rationale,expires_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, tenant, scope_kind, scope, target_mode.value, sequence,
                 actor.subject, approval_id, reason.strip(), expires_at),
            )
        return {"id": identifier, "mode": target_mode.value, "sequence": sequence,
                "expires_at": expires_at, "idempotent": False}

    def effective_mode(self, *, tenant_id: str, scope_kind: str = "company",
                       scope_id: str | None = None) -> dict:
        # Expired temporary restrictions fail safely to ACTIVE only when not in emergency.
        events = self.modes(tenant_id=tenant_id, scope_kind=scope_kind, scope_id=scope_id)
        if not events:
            return {"mode": "active", "source": "baseline", "expires_at": None}
        latest = events[0]
        if latest["expires_at"] and latest["expires_at"] <= datetime.now(timezone.utc):
            return {"mode": "expired_requires_review", "source": "expired_restriction",
                    "expires_at": latest["expires_at"], "sequence": latest["sequence"]}
        return {"mode": latest["mode"], "source": "approved_event",
                "expires_at": latest["expires_at"], "sequence": latest["sequence"]}

    def normalize_agent_evidence(self, *, employee_id: str, kind: str,
                                 label: str, value_int: int | None,
                                 evidence_ref: str, note: str) -> dict:
        payload, digest = agent_evidence_intent(
            employee_id=employee_id, kind=kind, label=label,
            value_int=value_int, evidence_ref=evidence_ref, note=note)
        return {"review_payload": payload, "intent_digest": digest}

    def propose_agent_evidence(self, *, actor: Principal, approval_id: str,
                               payload: dict, intent_digest: str) -> dict:
        normalized, digest = agent_evidence_intent(**payload)
        if digest != intent_digest:
            raise PermissionError("Agent evidence intent integrity failure")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            worker = self.connection.execute(
                """SELECT kind FROM ago_employees WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, normalized["employee_id"]),
            ).fetchone()
            if not worker or worker["kind"] != "ai":
                raise LookupError("Tenant AI worker not found")
            pending = self.connection.execute(
                """SELECT action,status,requester_id FROM ago_approval_requests
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            expected = ("enterprise:agent-evidence:" + normalized["employee_id"] +
                        ":" + digest)
            if (not pending or pending["action"] != expected
                or pending["status"] != "pending"
                or str(pending["requester_id"]) != actor.subject):
                raise PermissionError("Exact pending employee evidence approval missing")
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_agent_evidence_intents
                   (id,tenant_id,employee_id,actor_id,approval_id,kind,label,
                    value_int,evidence_ref,note,canonical_payload,digest)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, normalized["employee_id"],
                 actor.subject, str(UUID(approval_id)), normalized["kind"],
                 normalized["label"], normalized["value_int"],
                 normalized["evidence_ref"], normalized["note"],
                 json.dumps(normalized, sort_keys=True, separators=(",", ":")),
                 digest),
            )
        return {"id": identifier, "approval_id": str(UUID(approval_id)),
                "review_payload": normalized, "intent_digest": digest,
                "status": "awaiting_independent_review"}

    def apply_agent_evidence(self, *, actor: Principal, intent_id: str,
                             approval_id: str) -> dict:
        identifier = str(UUID(intent_id))
        review = str(UUID(approval_id))
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            row = self.connection.execute(
                """SELECT employee_id,actor_id,approval_id,digest
                   FROM ago_agent_evidence_intents
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, identifier),
            ).fetchone()
            if not row:
                raise LookupError("Evidence intent not found")
            if str(row["actor_id"]) != actor.subject or str(row["approval_id"]) != review:
                raise PermissionError("Cannot change evidence owner or approval")
            self._approval(actor, review,
                           "enterprise:agent-evidence:" +
                           str(row["employee_id"]) + ":" + row["digest"])
            existing = self.connection.execute(
                """SELECT id FROM ago_agent_evidence_events
                   WHERE tenant_id=%s AND intent_id=%s""",
                (actor.tenant_id, identifier),
            ).fetchone()
            if existing:
                return {"id": str(existing["id"]), "intent_id": identifier,
                        "idempotent": True, "permissions_granted": False}
            event_id = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_agent_evidence_events
                   (id,tenant_id,intent_id,approval_id,applied_by)
                   VALUES(%s,%s,%s,%s,%s)""",
                (event_id, actor.tenant_id, identifier, review, actor.subject),
            )
        return {"id": event_id, "intent_id": identifier,
                "idempotent": False, "permissions_granted": False}

    def agent_evidence(self, *, tenant_id: str, employee_id: str) -> list[dict]:
        return [dict(x) for x in self.connection.execute(
            """SELECT i.id,i.kind,i.label,i.value_int,i.evidence_ref,i.note,
                      i.digest,e.created_at AS reviewed_at,e.approval_id
               FROM ago_agent_evidence_events e
               JOIN ago_agent_evidence_intents i
                 ON i.tenant_id=e.tenant_id AND i.id=e.intent_id
               WHERE e.tenant_id=%s AND i.employee_id=%s
               ORDER BY e.created_at DESC,e.id DESC LIMIT 100""",
            (str(UUID(tenant_id)), str(UUID(employee_id))),
        ).fetchall()]

    def worker_state(self, *, tenant_id: str, employee_id: str) -> dict:
        tenant, employee = str(UUID(tenant_id)), str(UUID(employee_id))
        row = self.connection.execute(
            """SELECT id,name,kind,department_id,manager_id FROM ago_employees
               WHERE tenant_id=%s AND id=%s""", (tenant, employee),
        ).fetchone()
        if row is None:
            raise LookupError("Employee not found")
        tasks = self.connection.execute(
            """SELECT id,action,status,created_at
               FROM ago_governed_tasks WHERE tenant_id=%s AND assignee_id=%s
               ORDER BY created_at DESC,id LIMIT 100""", (tenant, employee),
        ).fetchall()
        active = sum(t["status"] == "running" for t in tasks)
        queued = sum(t["status"] in ("proposed", "waiting_approval", "ready") for t in tasks)
        current = [str(t["id"]) for t in tasks if t["status"] == "running"]
        future = [str(t["id"]) for t in tasks if t["status"] in (
            "proposed", "waiting_approval", "ready")]
        capacity = None  # no measured worker-unit capacity exists in legacy schema
        competence = self.agent_evidence(tenant_id=tenant, employee_id=employee)
        confidence = next((x["value_int"] for x in competence
                           if x["kind"] == "confidence"), None)
        open_help = [h for h in self.assistance(tenant_id=tenant, employee_id=employee)
                     if h["outcome"] != "resolved"]
        blocking_help = [h for h in open_help if h["severity"] == "blocking"]
        latest = self.worker_history(tenant_id=tenant, employee_id=employee)
        availability = latest[0]["state"] if latest else "available"
        return {
            "availability_state": availability,
            "id": employee, "name": row["name"], "kind": row["kind"],
            "department_id": str(row["department_id"]),
            "manager_id": str(row["manager_id"]) if row["manager_id"] else None,
            "current_tasks": current, "future_tasks": future,
            "active_count": active, "queued_count": queued,
            "capacity_units": capacity, "confidence": confidence,
            "confidence_calibrated": False,
            "skill_evidence": [x["label"] for x in competence if x["kind"] == "skill"],
            "knowledge_evidence": [x["label"] for x in competence
                                   if x["kind"] == "knowledge"],
            "permission_awareness": "requires_runtime_policy_evaluation",
            "learning_evidence": [x["evidence_ref"] for x in competence
                                  if x["kind"] == "learning"],
            "risk": "needs_policy_review" if any(
                x["kind"] == "risk" for x in competence) else "unassessed",
            "competence_evidence_count": len(competence),
            "stress": "operational_load_only", "subjective_consciousness": False,
            "help_needed": bool(open_help), "blocking_assistance": len(blocking_help),
            "open_assistance_count": len(open_help),
            "evidence_source": "ago_governed_tasks_and_employee_help_requests",
            "observed_at": datetime.now(timezone.utc),
        }

    def capture_worker(self, *, actor: Principal, employee_id: str,
                       available_units: int, source_ref: str) -> dict:
        if not 0 <= available_units <= 100000 or not 1 <= len(source_ref.strip()) <= 1024:
            raise ValueError("Valid capacity and evidence source required")
        state = self.worker_state(tenant_id=actor.tenant_id, employee_id=employee_id)
        load = operational_load(running=state["active_count"],
                                queued=state["queued_count"], capacity=available_units)
        state["load"] = load
        state["capacity_units"] = available_units
        state["observed_at"] = state["observed_at"].isoformat()
        from hashlib import sha256
        payload = json.dumps(state, sort_keys=True, default=str)
        digest = sha256((payload + "|" + source_ref).encode()).hexdigest()
        identifier = str(uuid4())
        with self.connection.transaction():
            self.connection.execute(
                """INSERT INTO ago_agent_state_snapshots
                   (id,tenant_id,employee_id,available_units,active_count,queued_count,
                    availability,state,evidence_digest,source_ref)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (identifier, actor.tenant_id, employee_id, available_units,
                 state["active_count"], state["queued_count"],
                 "available" if not load["overloaded"] else "unknown",
                 payload, digest, source_ref.strip()),
            )
        return {"id": identifier, "evidence_digest": digest, **state}

    def allocate_preview(self, *, tenant_id: str, employee_id: str,
                         available_units: int) -> dict:
        if not 0 <= available_units <= 100000:
            raise ValueError("Operator input capacity must be bounded")
        state = self.worker_state(tenant_id=tenant_id, employee_id=employee_id)
        scope_modes = [
            self.effective_mode(tenant_id=tenant_id)["mode"],
            self.effective_mode(tenant_id=tenant_id, scope_kind="department",
                                scope_id=state["department_id"])["mode"],
            self.effective_mode(tenant_id=tenant_id, scope_kind="employee",
                                scope_id=employee_id)["mode"],
        ]
        mode = next((x for x in scope_modes if x != "active"), "active")
        rows = self.connection.execute(
            """SELECT t.id,t.status,a.status AS approval_status
               FROM ago_governed_tasks t
               LEFT JOIN ago_approval_requests a
               ON a.tenant_id=t.tenant_id AND a.id=t.approval_id
               WHERE t.tenant_id=%s AND t.assignee_id=%s
               AND t.status IN ('proposed','waiting_approval','ready')
               ORDER BY t.created_at,t.id LIMIT 100""",
            (tenant_id, employee_id),
        ).fetchall()
        worker = WorkerState(state["availability_state"])
        items = [WorkCandidate(employee_id, str(row["id"]), 50,
                 available_units, 1, True,
                 row["status"] == "ready" and row["approval_status"] == "approved",
                 worker, 0) for row in rows]
        admitted = allocate(items, mode=OperatingMode.ACTIVE) if mode == "active" else ()
        return {"mode": mode, "worker_state": worker.value,
                "admitted_task_ids": [x.task_id for x in admitted],
                "queued": len(rows), "read_only": True,
                "capacity_source": "operator_input_not_measured",
                "unknown_dependencies": True, "not_authorized_to_start": True}


    def plan(self, *, actor: Principal, identifier: str, horizon: str,
             parent_id: str | None, title: str, starts_at: datetime,
             ends_at: datetime, budget_ceiling: str, approval_id: str,
             evidence_ref: str) -> dict:
        if horizon not in HORIZONS or not title.strip() or len(title) > 300:
            raise ValueError("Invalid horizon or title")
        if starts_at.tzinfo is None or ends_at.tzinfo is None or starts_at >= ends_at:
            raise ValueError("Valid timezone-aware window required")
        if not evidence_ref.strip() or len(evidence_ref) > 1024:
            raise ValueError("Planning evidence required")
        limit = Decimal(budget_ceiling)
        if not limit.is_finite() or limit < 0:
            raise ValueError("Invalid budget")
        identifier = str(UUID(identifier))
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, "enterprise:plan:" + identifier)
            if parent_id:
                parent = self.connection.execute(
                    """SELECT horizon,starts_at,ends_at,budget_ceiling
                       FROM ago_horizon_plans WHERE tenant_id=%s AND id=%s""",
                    (actor.tenant_id, str(UUID(parent_id))),
                ).fetchone()
                if parent is None:
                    raise LookupError("Parent plan not found")
                validate_horizon(parent["horizon"], horizon,
                                 parent_start=parent["starts_at"], parent_end=parent["ends_at"],
                                 child_start=starts_at, child_end=ends_at)
                if limit > parent["budget_ceiling"]:
                    raise PermissionError("Child budget exceeds parent ceiling")
            elif horizon != "lifetime":
                raise PermissionError("Only lifetime plans may be roots")
            self.connection.execute(
                """INSERT INTO ago_horizon_plans
                   (id,tenant_id,parent_id,owner_id,horizon,title,
                    starts_at,ends_at,budget_ceiling,approval_id,evidence_ref)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, parent_id, actor.subject,
                 horizon, title.strip(), starts_at, ends_at, limit,
                 approval_id, evidence_ref.strip()),
            )
        return {"id": identifier, "horizon": horizon, "status": "approved_recorded"}

    def plans(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT id,parent_id,owner_id,horizon,title,starts_at,ends_at,
                 budget_ceiling,revision,evidence_ref,created_at
                 FROM ago_horizon_plans WHERE tenant_id=%s
                 ORDER BY created_at,id LIMIT 500""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def record_cost(self, *, actor: Principal, operation_key: str, category: str,
                    provider: str, source_ref: str, amount: str, currency: str,
                    period_start: datetime, period_end: datetime) -> dict:
        if category not in ("model","storage","tool","execution","time","revenue","other"):
            raise ValueError("Invalid cost category")
        if not 1 <= len(operation_key.strip()) <= 200 or not provider.strip() or not source_ref.strip():
            raise ValueError("Evidence source and idempotency key required")
        if period_start.tzinfo is None or period_end.tzinfo is None or period_start >= period_end:
            raise ValueError("Invalid cost period")
        if len(currency) != 3 or not currency.isupper() or not currency.isalpha():
            raise ValueError("ISO currency code required")
        value = Decimal(amount)
        if value < 0 or not value.is_finite():
            raise ValueError("Invalid observed amount")
        identifier = str(uuid4())
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            prior = self.connection.execute(
                """SELECT id,source_ref,observed_amount FROM ago_observed_costs
                   WHERE tenant_id=%s AND provider=%s AND operation_key=%s""",
                (actor.tenant_id, provider, operation_key),
            ).fetchone()
            if prior:
                if prior["source_ref"] != source_ref or prior["observed_amount"] != value:
                    raise ValueError("Duplicate key conflicts with immutable cost evidence")
                return {"id": str(prior["id"]), "evidence_state": "unverified", "idempotent": True}
            self.connection.execute(
                """INSERT INTO ago_observed_costs
                   (id,tenant_id,operation_key,category,provider,source_ref,
                    observed_amount,currency,period_start,period_end,recorded_by)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, operation_key, category,
                 provider, source_ref, value, currency,
                 period_start, period_end, actor.subject),
            )
        return {"id": identifier, "evidence_state": "unverified", "idempotent": False,
                "financial_settlement": False}

    def costs(self, *, tenant_id: str) -> list[dict]:
        return [dict(x) for x in self.connection.execute(
            """SELECT id,category,provider,source_ref,observed_amount,currency,
                      evidence_state,period_start,period_end,recorded_at
               FROM ago_observed_costs WHERE tenant_id=%s
               ORDER BY recorded_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def create_budget(self, *, actor: Principal, identifier: str, approval_id: str,
                      scope_kind: str, scope_id: str | None,
                      ceiling: str, currency: str) -> dict:
        if scope_kind not in ("company","department","employee") or (
            (scope_kind == "company") != (scope_id is None)
        ):
            raise ValueError("Invalid budget scope")
        if len(currency) != 3 or not currency.isalpha() or not currency.isupper():
            raise ValueError("Invalid currency")
        identifier = str(UUID(identifier))
        value = Decimal(ceiling)
        if not value.is_finite() or value < 0:
            raise ValueError("Invalid spending ceiling")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, "enterprise:budget:" + identifier)
            previous = self.connection.execute(
                """SELECT id,scope_kind,scope_id,approved_ceiling,currency
                   FROM ago_budget_envelopes WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if previous:
                if (str(previous["id"]) != identifier or previous["scope_kind"] != scope_kind
                    or (str(previous["scope_id"]) if previous["scope_id"] else None) != (
                        str(UUID(scope_id)) if scope_id else None)
                    or previous["approved_ceiling"] != value or previous["currency"] != currency):
                    raise ValueError("Approval already bound to a different budget")
                return {"id": identifier, "ceiling": str(value),
                        "scope_kind": scope_kind, "idempotent": True}
            if scope_id:
                table = "ago_departments" if scope_kind == "department" else "ago_employees"
                target = self.connection.execute(
                    f"SELECT * FROM {table} WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, str(UUID(scope_id))),
                ).fetchone()
                if not target:
                    raise LookupError("Budget scope not found")
                parent_kind, parent_id = ("company", None) if scope_kind == "department" else (
                    "department", str(target["department_id"]))
                parent = self.connection.execute(
                    """SELECT approved_ceiling,currency FROM ago_budget_envelopes
                       WHERE tenant_id=%s AND scope_kind=%s
                         AND scope_id IS NOT DISTINCT FROM %s::uuid
                       ORDER BY created_at DESC,id DESC LIMIT 1""",
                    (actor.tenant_id, parent_kind, parent_id),
                ).fetchone()
                if not parent or parent["currency"] != currency or value > parent["approved_ceiling"]:
                    raise PermissionError("Parent budget absent, currency differs or envelope exceeded")
            self.connection.execute(
                """INSERT INTO ago_budget_envelopes
                   (id,tenant_id,scope_kind,scope_id,approved_ceiling,currency,approval_id)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, scope_kind, scope_id,
                 value, currency, approval_id),
            )
        return {"id": identifier, "ceiling": str(value), "scope_kind": scope_kind}

    def budgets(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT id,scope_kind,scope_id,approved_ceiling,currency,
                      approval_id,created_at FROM ago_budget_envelopes
               WHERE tenant_id=%s ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def _verify_marketplace_dependencies(self, *, tenant_id: str,
                                         manifest: dict, require_published: bool) -> None:
        """Fail closed on cross-tenant, expired or incompatible asset versions."""
        dependencies = manifest.get("dependencies", [])
        if not isinstance(dependencies, list) or len(dependencies) > 25:
            raise ValueError("Bounded dependency manifest list required")
        seen: set[str] = set()
        for item in dependencies:
            if not isinstance(item, dict) or set(item) != {"asset_id", "version", "digest"}:
                raise ValueError("Dependency requires exact asset ID, version and digest")
            identifier = str(UUID(item["asset_id"]))
            if identifier in seen:
                raise ValueError("Duplicate asset dependency")
            seen.add(identifier)
            version, digest = item["version"], item["digest"]
            if (not isinstance(version, str) or len(version.split(".")) != 3
                or not all(part.isdigit() for part in version.split("."))):
                raise ValueError("Unsupported dependency version")
            if (not isinstance(digest, str) or len(digest) != 64
                or any(char not in "0123456789abcdef" for char in digest)):
                raise ValueError("Invalid dependency content digest")
            if require_published:
                row = self.connection.execute(
                    """SELECT version,digest,status FROM ago_marketplace_assets
                       WHERE tenant_id=%s AND id=%s""",
                    (tenant_id, identifier),
                ).fetchone()
                if (not row or row["status"] != "published"
                    or row["version"] != version or row["digest"] != digest):
                    raise PermissionError("Dependency not published or version/digest mismatch")

    def asset_draft(self, *, actor: Principal, department_id: str, name: str,
                    kind: str, version: str, license_id: str,
                    digest: str, manifest: dict) -> dict:
        identity = AssetIdentity(actor.tenant_id, actor.subject, name, kind,
                                 version, license_id, digest)
        identity.validate()
        if not isinstance(manifest, dict) or len(json.dumps(manifest)) > 16000:
            raise ValueError("Bounded asset manifest required")
        self._verify_marketplace_dependencies(
            tenant_id=actor.tenant_id, manifest=manifest, require_published=False)
        identifier = str(uuid4())
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            owner = self.connection.execute(
                "SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, str(UUID(department_id))),
            ).fetchone()
            if not owner:
                raise LookupError("Asset-owning department missing")
            self.connection.execute(
                """INSERT INTO ago_marketplace_assets
                   (id,tenant_id,owner_department_id,publisher_id,name,
                    asset_kind,version,digest,license_id,manifest)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                (identifier, actor.tenant_id, department_id,
                 actor.subject, name, kind, version, digest, license_id,
                 json.dumps(manifest, sort_keys=True)),
            )
        return {"id": identifier, "status": "draft", "external_marketplace": False}

    def assets(self, *, tenant_id: str, kind: str | None = None) -> list[dict]:
        if kind and kind not in ASSET_TYPES:
            raise ValueError("Unsupported asset kind")
        return [dict(row) for row in self.connection.execute(
            """SELECT id,name,asset_kind,version,digest,license_id,
                    owner_department_id,publisher_id,status,manifest,created_at
               FROM ago_marketplace_assets WHERE tenant_id=%s
                 AND (%s::text IS NULL OR asset_kind=%s)
               ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)), kind, kind),
        ).fetchall()]

    def asset_payload_upload(self, *, actor: Principal, asset_id: str,
                             content_base64: str, content_type: str) -> dict:
        allowed_types = {"text/plain", "text/markdown", "application/json",
                         "application/octet-stream"}
        if content_type not in allowed_types or len(content_base64) > 1400000:
            raise ValueError("Unsupported or oversized internal asset content")
        try:
            raw = base64.b64decode(content_base64, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise ValueError("Payload must be strict base64") from exc
        if not 1 <= len(raw) <= 1048576:
            raise ValueError("Internal asset payload limited to 1 MiB")
        from hashlib import sha256
        digest = sha256(raw).hexdigest()
        identifier = str(UUID(asset_id))
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            asset = self.connection.execute(
                """SELECT publisher_id,status,digest FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, identifier),
            ).fetchone()
            if not asset:
                raise LookupError("Internal asset not found")
            if asset["status"] != "draft" or str(asset["publisher_id"]) != actor.subject:
                raise PermissionError("Only draft publisher can upload asset bytes")
            if digest != asset["digest"]:
                raise PermissionError("Payload digest differs from immutable catalog identity")
            previous = self.connection.execute(
                """SELECT id,content_type,digest FROM ago_marketplace_payloads
                   WHERE tenant_id=%s AND asset_id=%s""",
                (actor.tenant_id, identifier),
            ).fetchone()
            if previous:
                if previous["content_type"] != content_type or previous["digest"] != digest:
                    raise PermissionError("Immutable internal asset payload already exists")
                return {"id": str(previous["id"]), "asset_id": identifier,
                        "digest": digest, "idempotent": True}
            row_id = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_marketplace_payloads
                   (id,tenant_id,asset_id,publisher_id,content_type,payload,digest)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (row_id, actor.tenant_id, identifier, actor.subject,
                 content_type, raw, digest),
            )
        return {"id": row_id, "asset_id": identifier,
                "bytes": len(raw), "digest": digest, "idempotent": False,
                "execution_granted": False}

    def asset_payload_read(self, *, actor: Principal, asset_id: str) -> dict:
        identifier = str(UUID(asset_id))
        meta = self.connection.execute(
            """SELECT publisher_id,status FROM ago_marketplace_assets
               WHERE tenant_id=%s AND id=%s""",
            (actor.tenant_id, identifier),
        ).fetchone()
        if not meta:
            raise LookupError("Asset not found")
        if str(meta["publisher_id"]) != actor.subject:
            if meta["status"] != "published":
                raise PermissionError("Unpublished or retired content inaccessible")
            permission = self.connection.execute(
                """SELECT 1 FROM ago_asset_consumptions WHERE tenant_id=%s
                   AND asset_id=%s AND actor_id=%s LIMIT 1""",
                (actor.tenant_id, identifier, actor.subject),
            ).fetchone()
            if not permission:
                raise PermissionError("Independent asset consumption approval required")
        saved = self.connection.execute(
            """SELECT content_type,payload,digest FROM ago_marketplace_payloads
               WHERE tenant_id=%s AND asset_id=%s""",
            (actor.tenant_id, identifier),
        ).fetchone()
        if not saved:
            raise LookupError("No verifiable local payload available")
        content = bytes(saved["payload"])
        from hashlib import sha256
        if sha256(content).hexdigest() != saved["digest"]:
            raise PermissionError("Historical content failed digest verification")
        return {"asset_id": identifier, "content_type": saved["content_type"],
                "digest": saved["digest"], "bytes": len(content),
                "content_base64": base64.b64encode(content).decode("ascii"),
                "execution_granted": False}

    def asset_propose(self, *, actor: Principal, asset_id: str, approval_id: str) -> dict:
        with self.connection.transaction():
            asset = self.connection.execute(
                """SELECT status,publisher_id FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone()
            if not asset:
                raise LookupError("Marketplace asset not found")
            if asset["status"] != "draft" or str(asset["publisher_id"]) != actor.subject:
                raise PermissionError("Only publisher can submit an unreviewed draft")
            request = self.connection.execute(
                """SELECT requester_id,status,action FROM ago_approval_requests
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if (not request or str(request["requester_id"]) != actor.subject or
                request["status"] != "pending" or request["action"] != "enterprise:publish:" + asset_id):
                raise PermissionError("Exact pending independent review required")
            self.connection.execute(
                """UPDATE ago_marketplace_assets SET status='proposed',approval_id=%s
                   WHERE tenant_id=%s AND id=%s""",
                (approval_id, actor.tenant_id, asset_id),
            )
        return {"id": asset_id, "status": "proposed"}

    def asset_publish(self, *, actor: Principal, asset_id: str) -> dict:
        with self.connection.transaction():
            asset = self.connection.execute(
                """SELECT approval_id,publisher_id,status,manifest FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone()
            if not asset:
                raise LookupError("Asset not found")
            if asset["status"] != "proposed" or str(asset["publisher_id"]) != actor.subject:
                raise PermissionError("Only publisher can reconcile proposed asset")
            self._approval(actor, str(asset["approval_id"]),
                           "enterprise:publish:" + asset_id)
            self._verify_marketplace_dependencies(
                tenant_id=actor.tenant_id, manifest=asset["manifest"],
                require_published=True)
            if asset["manifest"].get("payload_required") is True and not self.connection.execute(
                """SELECT 1 FROM ago_marketplace_payloads
                   WHERE tenant_id=%s AND asset_id=%s""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone():
                raise PermissionError("Checksum-verified payload required to publish")
            self.connection.execute(
                """UPDATE ago_marketplace_assets SET status='published'
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, asset_id),
            )
        return {"id": asset_id, "status": "published"}

    def asset_consume(self, *, actor: Principal, asset_id: str,
                      department_id: str, approval_id: str, evidence_ref: str) -> dict:
        if not evidence_ref.strip() or len(evidence_ref) > 1024:
            raise ValueError("Consumption evidence required")
        identifier = str(uuid4())
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, "enterprise:consume:" + asset_id)
            previous = self.connection.execute(
                """SELECT id,asset_id,consumer_department_id,evidence_ref
                   FROM ago_asset_consumptions
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if previous:
                if (str(previous["asset_id"]) != str(UUID(asset_id))
                    or str(previous["consumer_department_id"]) != str(UUID(department_id))
                    or previous["evidence_ref"] != evidence_ref.strip()):
                    raise ValueError("Approval already consumed by different immutable asset use")
                return {"id": str(previous["id"]), "asset_id": asset_id,
                        "status": "recorded", "execution_granted": False,
                        "idempotent": True}
            selected_asset = self.connection.execute(
                """SELECT manifest FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s AND status='published'""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone()
            if not selected_asset:
                raise PermissionError("Only active tenant-owned published asset may be used")
            self._verify_marketplace_dependencies(
                tenant_id=actor.tenant_id, manifest=selected_asset["manifest"],
                require_published=True)
            if not self.connection.execute(
                """SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, str(UUID(department_id))),
            ).fetchone():
                raise LookupError("Consuming department not found")
            self.connection.execute(
                """INSERT INTO ago_asset_consumptions
                   (id,tenant_id,asset_id,consumer_department_id,actor_id,
                    approval_id,evidence_ref)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, asset_id, department_id, actor.subject,
                 approval_id, evidence_ref.strip()),
            )
        return {"id": identifier, "asset_id": asset_id, "status": "recorded",
                "execution_granted": False}

    def asset_usage(self, *, tenant_id: str) -> list[dict]:
        return [dict(r) for r in self.connection.execute(
            """SELECT asset_id,count(*) AS consumptions FROM ago_asset_consumptions
               WHERE tenant_id=%s GROUP BY asset_id ORDER BY consumptions DESC,asset_id
               LIMIT 100""", (str(UUID(tenant_id)),),
        ).fetchall()]

    def evolution_observation(self, *, actor: Principal, baseline: list[str],
                              candidate: list[str], evidence: list[dict],
                              source_snapshot_id: str) -> dict:
        observed = evaluate_change(baseline=baseline, candidate=candidate, evidence=evidence)
        with self.connection.transaction():
            if not self.connection.execute(
                """SELECT 1 FROM ago_executive_snapshots WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, str(UUID(source_snapshot_id))),
            ).fetchone():
                raise LookupError("Real source snapshot not found")
            from hashlib import sha256
            before = sha256(json.dumps(baseline).encode()).hexdigest()
            after = sha256(json.dumps(candidate).encode()).hexdigest()
            if before == after:
                raise ValueError("Candidate needs a different documented result")
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_evolution_observations
                   (id,tenant_id,baseline_digest,candidate_digest,metrics,source_ref)
                   VALUES (%s,%s,%s,%s,%s::jsonb,%s)""",
                (identifier, actor.tenant_id, before, after,
                 json.dumps(observed, sort_keys=True), "snapshot:" + source_snapshot_id),
            )
        return {"id": identifier, "status": "unreviewed", **observed}

    def twin(self, *, actor: Principal, snapshot_id: str, actions: int,
             cost_per_action: str, budget: str, failure_pct: int,
             hiring: int = 0, layoffs: int = 0, market_shock_pct: int = 0) -> dict:
        with self.connection.transaction():
            snap = self.connection.execute(
                """SELECT digest,created_at,metrics FROM ago_executive_snapshots
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, str(UUID(snapshot_id))),
            ).fetchone()
            if not snap:
                raise LookupError("Snapshot not found")
            # Scenario state MUST come from the immutable captured snapshot.
            # Current live headcount would corrupt historical provenance.
            observed_org = snap["metrics"].get("organization_observation", {})
            count = observed_org.get("ai_employees")
            if type(count) is not int or not 0 <= count <= 100000:
                raise ValueError("Snapshot does not contain valid historical workforce count")
            model = twin_scenario(
                workers=count, actions=actions, cost_per_action=cost_per_action,
                budget=budget, failure_pct=failure_pct, hiring=hiring, layoffs=layoffs,
                market_shock_pct=market_shock_pct, observed_samples=0,
            )
            model["snapshot_created_at"] = snap["created_at"].isoformat()
            model["snapshot_workers"] = count
            model["snapshot_age_seconds"] = max(
                0, int((datetime.now(timezone.utc) - snap["created_at"]).total_seconds()))
            model["data_coverage"] = "partial"
            model["snapshot_source"] = "immutable_executive_metrics"
            assumptions = {
                "actions": actions, "cost_per_action": cost_per_action, "budget": budget,
                "failure_pct": failure_pct, "hiring": hiring, "layoffs": layoffs,
                "market_shock_pct": market_shock_pct
            }
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_twin_scenarios
                   (id,tenant_id,snapshot_id,actor_id,assumptions,result,
                    data_coverage,calibrated,source_digest)
                   VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb,'partial',false,%s)""",
                (identifier, actor.tenant_id, snapshot_id, actor.subject,
                 json.dumps(assumptions, sort_keys=True),
                 json.dumps(model, sort_keys=True), snap["digest"]),
            )
        return {"id": identifier, "snapshot_id": snapshot_id, **model}


    def worker_transition(self, *, actor: Principal, employee_id: str,
                          state: str, approval_id: str, reason: str,
                          expires_at: datetime | None = None) -> dict:
        employee = str(UUID(employee_id))
        target = WorkerState(state)
        if not reason.strip() or len(reason) > 3000:
            raise ValueError("Worker transition rationale required")
        if target in (WorkerState.PAUSED, WorkerState.SLEEPING, WorkerState.INTERRUPTED):
            now = datetime.now(timezone.utc)
            if not expires_at or expires_at.tzinfo is None or not (
                now < expires_at <= now + timedelta(days=7)
            ):
                raise ValueError("Temporary worker restriction needs bounded expiry")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            row = self.connection.execute(
                """SELECT kind FROM ago_employees WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, employee),
            ).fetchone()
            if not row:
                raise LookupError("Worker not found")
            if row["kind"] != "ai":
                raise PermissionError("OOS automated control applies to AI workers only")
            prior_use = self.connection.execute(
                """SELECT id,state,sequence FROM ago_worker_state_events
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if prior_use:
                return dict(prior_use) | {"idempotent": True}
            self._approval(actor, approval_id, "enterprise:worker:" + employee + ":" + state)
            previous = self.connection.execute(
                """SELECT state,sequence FROM ago_worker_state_events
                   WHERE tenant_id=%s AND employee_id=%s ORDER BY sequence DESC LIMIT 1""",
                (actor.tenant_id, employee),
            ).fetchone()
            old_state = WorkerState(previous["state"]) if previous else WorkerState.AVAILABLE
            transition_worker(old_state, target, approved=True, reason=reason)
            identifier = str(uuid4())
            sequence = (int(previous["sequence"]) + 1) if previous else 1
            self.connection.execute(
                """INSERT INTO ago_worker_state_events
                   (id,tenant_id,employee_id,actor_id,approval_id,state,sequence,reason,expires_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, employee, actor.subject,
                 approval_id, target.value, sequence, reason.strip(), expires_at),
            )
        return {"id": identifier, "employee_id": employee, "state": state,
                "sequence": sequence, "idempotent": False}

    def worker_history(self, *, tenant_id: str, employee_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            """SELECT id,employee_id,state,sequence,reason,expires_at,created_at,approval_id
               FROM ago_worker_state_events WHERE tenant_id=%s AND employee_id=%s
               ORDER BY sequence DESC LIMIT 100""",
            (str(UUID(tenant_id)), str(UUID(employee_id))),
        ).fetchall()]

    def asset_retire(self, *, actor: Principal, asset_id: str, target_state: str,
                     approval_id: str, reason: str) -> dict:
        if target_state not in ("deprecated", "revoked") or not reason.strip() or len(reason) > 3000:
            raise ValueError("Valid asset retirement reason and target required")
        asset_id = str(UUID(asset_id))
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            row = self.connection.execute(
                """SELECT publisher_id,status FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, asset_id),
            ).fetchone()
            if not row:
                raise LookupError("Asset missing")
            previous = self.connection.execute(
                """SELECT id,asset_id,target_state,reason FROM ago_marketplace_lifecycle_events
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if previous:
                if (str(previous["asset_id"]) != asset_id
                    or previous["target_state"] != target_state
                    or previous["reason"] != reason.strip()):
                    raise ValueError("Approval already used for a different lifecycle event")
                return {"id": asset_id, "status": target_state,
                        "event_id": str(previous["id"]), "idempotent": True}
            if str(row["publisher_id"]) != actor.subject or (
                (row["status"] == "published" and target_state not in ("deprecated", "revoked"))
                or (row["status"] == "deprecated" and target_state != "revoked")
                or row["status"] not in ("published", "deprecated")
            ):
                raise PermissionError("Invalid asset state or unauthorized owner")
            self._approval(actor, approval_id,
                           "enterprise:asset:" + asset_id + ":" + target_state)
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_marketplace_lifecycle_events
                   (id,tenant_id,asset_id,actor_id,approval_id,target_state,reason)
                   VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, asset_id, actor.subject, approval_id,
                 target_state, reason.strip()),
            )
            self.connection.execute(
                """UPDATE ago_marketplace_assets SET status=%s,approval_id=%s
                   WHERE tenant_id=%s AND id=%s""",
                (target_state, approval_id, actor.tenant_id, asset_id),
            )
        return {"id": asset_id, "status": target_state, "event_id": identifier}


    def request_assistance(self, *, actor: Principal, employee_id: str,
                           task_id: str | None, reason: str, severity: str,
                           summary: str, evidence_ref: str) -> dict:
        if reason not in ("overload", "low_confidence", "missing_permission",
                          "dependency", "safety_risk", "assistance"):
            raise ValueError("Unknown assistance cause")
        if severity not in ("advisory", "blocking"):
            raise ValueError("Unknown assistance severity")
        if not 1 <= len(summary.strip()) <= 1500 or not 1 <= len(evidence_ref.strip()) <= 1024:
            raise ValueError("Bounded summary and real evidence reference required")
        employee = str(UUID(employee_id))
        task = str(UUID(task_id)) if task_id else None
        identifier = str(uuid4())
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            worker = self.connection.execute(
                """SELECT kind FROM ago_employees WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, employee),
            ).fetchone()
            if not worker or worker["kind"] != "ai":
                raise LookupError("Tenant AI employee missing")
            if task and not self.connection.execute(
                """SELECT 1 FROM ago_governed_tasks
                   WHERE tenant_id=%s AND id=%s AND assignee_id=%s""",
                (actor.tenant_id, task, employee),
            ).fetchone():
                raise PermissionError("Task must be assigned to this employee")
            self.connection.execute(
                """INSERT INTO ago_employee_help_requests
                   (id,tenant_id,employee_id,task_id,submitted_by,reason,severity,summary,evidence_ref)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, employee, task, actor.subject,
                 reason, severity, summary.strip(), evidence_ref.strip()),
            )
        return {"id": identifier, "employee_id": employee, "severity": severity,
                "status": "open", "execution_guard": severity == "blocking"}

    def assistance(self, *, tenant_id: str, employee_id: str | None = None) -> list[dict]:
        if employee_id:
            UUID(employee_id)
        return [dict(row) for row in self.connection.execute(
            """SELECT h.id,h.employee_id,h.task_id,h.reason,h.severity,h.summary,
                      h.evidence_ref,h.created_at,d.outcome,d.explanation,
                      d.created_at AS decided_at
               FROM ago_employee_help_requests h
               LEFT JOIN ago_employee_help_decisions d ON d.tenant_id=h.tenant_id
                 AND d.request_id=h.id
               WHERE h.tenant_id=%s AND (%s::uuid IS NULL OR h.employee_id=%s)
               ORDER BY h.created_at DESC,h.id LIMIT 100""",
            (str(UUID(tenant_id)), employee_id, employee_id),
        ).fetchall()]

    def resolve_assistance(self, *, actor: Principal, request_id: str,
                           approval_id: str, outcome: str, explanation: str) -> dict:
        request = str(UUID(request_id))
        if outcome not in ("resolved", "rejected") or not 1 <= len(explanation.strip()) <= 1500:
            raise ValueError("Reviewed outcome and explanation required")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            earlier = self.connection.execute(
                """SELECT id,approval_id,outcome,explanation FROM ago_employee_help_decisions
                   WHERE tenant_id=%s AND request_id=%s""",
                (actor.tenant_id, request),
            ).fetchone()
            if earlier:
                if (str(earlier["approval_id"]) != str(UUID(approval_id))
                    or earlier["outcome"] != outcome
                    or earlier["explanation"] != explanation.strip()):
                    raise PermissionError("Assistance decision is already immutable")
                return {"id": str(earlier["id"]), "request_id": request,
                        "outcome": outcome, "idempotent": True}
            if not self.connection.execute(
                "SELECT 1 FROM ago_employee_help_requests WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, request),
            ).fetchone():
                raise LookupError("Assistance request not found")
            self._approval(actor, approval_id, "enterprise:help:resolve:" + request)
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_employee_help_decisions
                   (id,tenant_id,request_id,actor_id,approval_id,outcome,explanation)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, request, actor.subject,
                 str(UUID(approval_id)), outcome, explanation.strip()),
            )
        return {"id": identifier, "request_id": request,
                "outcome": outcome, "idempotent": False}

    def link_plan_task(self, *, actor: Principal, horizon_plan_id: str, task_id: str,
                       approval_id: str, evidence_ref: str) -> dict:
        horizon, task = str(UUID(horizon_plan_id)), str(UUID(task_id))
        if not 1 <= len(evidence_ref.strip()) <= 1024:
            raise ValueError("Plan-task evidence required")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            before = self.connection.execute(
                """SELECT id,approval_id,evidence_ref FROM ago_horizon_task_links
                   WHERE tenant_id=%s AND horizon_plan_id=%s AND task_id=%s""",
                (actor.tenant_id, horizon, task),
            ).fetchone()
            if before:
                if str(before["approval_id"]) != str(UUID(approval_id)) or (
                    before["evidence_ref"] != evidence_ref.strip()
                ):
                    raise PermissionError("Cannot rewrite approved plan/task lineage")
                return {"id": str(before["id"]), "idempotent": True}
            self._approval(actor, approval_id,
                           "enterprise:plan-task:" + horizon + ":" + task)
            plan = self.connection.execute(
                """SELECT starts_at,ends_at FROM ago_horizon_plans
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, horizon),
            ).fetchone()
            work = self.connection.execute(
                """SELECT created_at FROM ago_governed_tasks
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, task),
            ).fetchone()
            if not plan or not work:
                raise LookupError("Approved horizon plan or tenant task missing")
            if not plan["starts_at"] <= work["created_at"] <= plan["ends_at"]:
                raise PermissionError("Task cannot be attributed outside plan window")
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_horizon_task_links
                   (id,tenant_id,horizon_plan_id,task_id,actor_id,approval_id,evidence_ref)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, horizon, task,
                 actor.subject, str(UUID(approval_id)), evidence_ref.strip()),
            )
        return {"id": identifier, "horizon_plan_id": horizon, "task_id": task,
                "idempotent": False, "execution_authorized": False}

    def plan_feedback(self, *, tenant_id: str, horizon_plan_id: str) -> dict:
        horizon = str(UUID(horizon_plan_id))
        if not self.connection.execute(
            "SELECT 1 FROM ago_horizon_plans WHERE tenant_id=%s AND id=%s",
            (str(UUID(tenant_id)), horizon),
        ).fetchone():
            raise LookupError("Plan not found")
        rows = self.connection.execute(
            """SELECT t.id,t.status,r.verdict
               FROM ago_horizon_task_links l
               JOIN ago_governed_tasks t ON t.tenant_id=l.tenant_id AND t.id=l.task_id
               LEFT JOIN ago_task_reviews r ON r.tenant_id=t.tenant_id AND r.task_id=t.id
               WHERE l.tenant_id=%s AND l.horizon_plan_id=%s
               ORDER BY t.created_at,t.id""",
            (str(UUID(tenant_id)), horizon),
        ).fetchall()
        counts = {"qa_passed": 0, "qa_failed": 0, "awaiting_qa": 0}
        for row in rows:
            if row["status"] == "completed" and row["verdict"] == "pass":
                counts["qa_passed"] += 1
            elif row["status"] == "failed" or row["verdict"] == "fail":
                counts["qa_failed"] += 1
            else:
                counts["awaiting_qa"] += 1
        return {"horizon_plan_id": horizon, "linked_tasks": len(rows), **counts,
                "status": "no_evidence" if not rows else "observed",
                "source": "governed_tasks_and_independent_QA",
                "replan_is_advisory": True, "automatically_replanned": False}


    def normalize_organization_intent(self, *, change_kind: str, target_id: str,
                                      reason: str, department_id: str | None = None,
                                      name: str | None = None,
                                      manager_id: str | None = None,
                                      role_level: int | None = None) -> dict:
        payload, digest = organization_change_intent(
            change_kind=change_kind, target_id=target_id, reason=reason,
            department_id=department_id, name=name,
            manager_id=manager_id, role_level=role_level)
        return {"review_payload": payload, "intent_digest": digest}

    def record_organization_intent(self, *, actor: Principal, approval_id: str,
                                   payload: dict, intent_digest: str) -> dict:
        """Persist the exact payload the other human will actually review."""
        normalized, recalculated = organization_change_intent(**payload)
        if recalculated != intent_digest:
            raise PermissionError("Unverifiable organizational proposal")
        entity = ("department" if normalized["change_kind"] in ("created","closed")
                  else "hr")
        expected = ("enterprise:" + entity + ":" + normalized["change_kind"] +
                    ":" + normalized["target_id"] + ":" + intent_digest)
        with self.connection.transaction():
            approval = self.connection.execute(
                """SELECT action,status,requester_id FROM ago_approval_requests
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if (not approval or approval["action"] != expected
                or approval["status"] != "pending"
                or str(approval["requester_id"]) != actor.subject):
                raise PermissionError("Matching pending founder proposal required")
            encoded = json.dumps(normalized, sort_keys=True, separators=(",", ":"))
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_organization_review_intents
                   (id,tenant_id,approval_id,actor_id,target_id,change_kind,
                    payload_key,payload,digest)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (identifier, actor.tenant_id, str(UUID(approval_id)),
                 actor.subject, normalized["target_id"], normalized["change_kind"],
                 encoded, encoded, intent_digest),
            )
        return {"id": identifier, "approval_id": str(UUID(approval_id)),
                "review_payload": normalized, "intent_digest": intent_digest}

    def organization_intents(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            """SELECT i.id,i.approval_id,i.change_kind,i.target_id,i.payload,
                      i.digest,i.created_at,a.status,a.reviewer_id
               FROM ago_organization_review_intents i
               JOIN ago_approval_requests a ON a.tenant_id=i.tenant_id
                 AND a.id=i.approval_id
               WHERE i.tenant_id=%s ORDER BY i.created_at DESC,i.id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def capacity_limits(self, *, tenant_id: str) -> dict:
        tenant = str(UUID(tenant_id))
        policies = [dict(row) for row in self.connection.execute(
            """SELECT id,scope_kind,scope_id,max_running,actor_id,approval_id,
                      rationale,created_at FROM ago_oos_capacity_policies
               WHERE tenant_id=%s ORDER BY created_at DESC,id DESC LIMIT 100""",
            (tenant,),
        ).fetchall()]
        current: dict[tuple[str, str | None], int] = {}
        for policy in policies:
            scope = (policy["scope_kind"],
                     str(policy["scope_id"]) if policy["scope_id"] else None)
            current.setdefault(scope, int(policy["max_running"]))
        running = [dict(x) for x in self.connection.execute(
            """SELECT e.department_id,t.assignee_id,count(*) AS running
               FROM ago_governed_tasks t
               JOIN ago_employees e ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id
               WHERE t.tenant_id=%s AND t.status='running'
               GROUP BY e.department_id,t.assignee_id""",
            (tenant,),
        ).fetchall()]
        return {
            "defaults": {"company": 12, "department": 4, "employee": 1},
            "policies": policies, "running": running,
            "total_running": sum(int(item["running"]) for item in running),
            "max_policies_returned": 100,
            "changes_require_independent_review": True,
        }

    def set_capacity(self, *, actor: Principal, approval_id: str,
                     scope_kind: str, scope_id: str | None, max_running: int,
                     rationale: str) -> dict:
        if scope_kind not in ("company","department","employee") or (
            (scope_kind == "company") != (scope_id is None)
        ):
            raise ValueError("Invalid capacity scope")
        if type(max_running) is not int or not 1 <= max_running <= 1000:
            raise ValueError("Invalid bounded running capacity")
        if not 1 <= len(rationale.strip()) <= 1500:
            raise ValueError("Reviewed capacity rationale required")
        scope = str(UUID(scope_id)) if scope_id else None
        action = ("enterprise:capacity:" + scope_kind + ":" +
                  (scope or "company") + ":" + str(max_running))
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, action)
            previously = self.connection.execute(
                """SELECT id,scope_kind,scope_id,max_running,rationale
                   FROM ago_oos_capacity_policies
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if previously:
                if (previously["scope_kind"] != scope_kind
                    or (str(previously["scope_id"]) if previously["scope_id"] else None) != scope
                    or previously["max_running"] != max_running
                    or previously["rationale"] != rationale.strip()):
                    raise PermissionError("Approval already bound to a different capacity")
                return {"id": str(previously["id"]),
                        "max_running": max_running, "idempotent": True}
            department_id = None
            if scope:
                source = ("ago_departments" if scope_kind == "department"
                          else "ago_employees")
                row = self.connection.execute(
                    f"SELECT * FROM {source} WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, scope),
                ).fetchone()
                if row is None:
                    raise LookupError("Capacity target does not belong to tenant")
                if scope_kind == "employee":
                    department_id = str(row["department_id"])
            def cap(level: str, identifier: str | None, fallback: int) -> int:
                found = self.connection.execute(
                    """SELECT max_running FROM ago_oos_capacity_policies
                       WHERE tenant_id=%s AND scope_kind=%s
                         AND scope_id IS NOT DISTINCT FROM %s::uuid
                       ORDER BY created_at DESC,id DESC LIMIT 1""",
                    (actor.tenant_id, level, identifier),
                ).fetchone()
                return int(found["max_running"]) if found else fallback
            if scope_kind == "department" and max_running > cap("company", None, 12):
                raise PermissionError("Department capacity exceeds company cap")
            if scope_kind == "employee" and (
                max_running > cap("department", department_id, 4)
                or max_running > cap("company", None, 12)
            ):
                raise PermissionError("Employee capacity exceeds parent scope")
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_oos_capacity_policies
                   (id,tenant_id,scope_kind,scope_id,max_running,actor_id,approval_id,rationale)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, scope_kind, scope, max_running,
                 actor.subject, str(UUID(approval_id)), rationale.strip()),
            )
        return {"id": identifier, "max_running": max_running,
                "scope_kind": scope_kind, "idempotent": False,
                "effective_on_next_task_admission": True}

    def organization_change(self, *, actor: Principal, change_kind: str,
                            target_id: str, approval_id: str, reason: str,
                            department_id: str | None = None,
                            name: str | None = None, manager_id: str | None = None,
                            role_level: int | None = None) -> dict:
        """Apply a reviewed organizational change, preserving prior records."""
        if change_kind not in ("hired", "promoted", "terminated", "created", "closed"):
            raise ValueError("Unknown organizational change")
        if not 1 <= len(reason.strip()) <= 2000:
            raise ValueError("Bounded organizational reason required")
        target = str(UUID(target_id))
        dept = str(UUID(department_id)) if department_id else None
        manager = str(UUID(manager_id)) if manager_id else None
        if role_level is not None and (type(role_level) is not int or not 1 <= role_level <= 5):
            raise ValueError("Role level out of bounds")
        intent, digest = organization_change_intent(
            change_kind=change_kind, target_id=target, reason=reason,
            department_id=dept, name=name, manager_id=manager,
            role_level=role_level)
        entity = "department" if change_kind in ("created", "closed") else "hr"
        action = "enterprise:" + entity + ":" + change_kind + ":" + target + ":" + digest
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            review = self.connection.execute(
                """SELECT payload,digest FROM ago_organization_review_intents
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if (not review or review["digest"] != digest
                or review["payload"] != intent):
                raise PermissionError("Organizational action differs from human-reviewed payload")
            self._approval(actor, approval_id, action)
            table = ("ago_department_lifecycle_events" if entity == "department"
                     else "ago_personnel_events")
            earlier = self.connection.execute(
                f"""SELECT id,reason FROM {table}
                   WHERE tenant_id=%s AND approval_id=%s""",
                (actor.tenant_id, str(UUID(approval_id))),
            ).fetchone()
            if earlier:
                if earlier["reason"] != reason.strip():
                    raise PermissionError("Cannot replay altered organizational approval")
                return {"id": str(earlier["id"]), "target_id": target,
                        "change_kind": change_kind, "idempotent": True}
            if change_kind == "created":
                if not name or not 1 <= len(name.strip()) <= 200:
                    raise ValueError("Department name required")
                self.connection.execute(
                    "INSERT INTO ago_departments(id,tenant_id,name) VALUES(%s,%s,%s)",
                    (target, actor.tenant_id, name.strip()),
                )
            elif change_kind == "closed":
                if not self.connection.execute(
                    "SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, target),
                ).fetchone():
                    raise LookupError("Department not found")
                if self.connection.execute(
                    """SELECT 1 FROM ago_employees WHERE tenant_id=%s AND department_id=%s
                       LIMIT 1""", (actor.tenant_id, target),
                ).fetchone():
                    raise PermissionError("Cannot close department containing employees")
            elif change_kind == "hired":
                if not dept or not name or not 1 <= len(name.strip()) <= 200:
                    raise ValueError("AI hire requires department and name")
                if self.connection.execute(
                    """SELECT 1 FROM ago_department_lifecycle_events
                       WHERE tenant_id=%s AND department_id=%s AND action='closed'""",
                    (actor.tenant_id, dept),
                ).fetchone():
                    raise PermissionError("Cannot hire into closed department")
                if not self.connection.execute(
                    "SELECT 1 FROM ago_departments WHERE tenant_id=%s AND id=%s",
                    (actor.tenant_id, dept),
                ).fetchone():
                    raise LookupError("Department does not exist")
                if manager and not self.connection.execute(
                    """SELECT 1 FROM ago_employees WHERE tenant_id=%s
                       AND department_id=%s AND id=%s""",
                    (actor.tenant_id, dept, manager),
                ).fetchone():
                    raise PermissionError("Manager must belong to same department")
                self.connection.execute(
                    """INSERT INTO ago_employees(id,tenant_id,department_id,
                       name,kind,manager_id) VALUES(%s,%s,%s,%s,'ai',%s)""",
                    (target, actor.tenant_id, dept, name.strip(), manager),
                )
            else:
                employee = self.connection.execute(
                    """SELECT id,kind FROM ago_employees
                       WHERE tenant_id=%s AND id=%s""",
                    (actor.tenant_id, target),
                ).fetchone()
                if not employee or employee["kind"] != "ai":
                    raise LookupError("AI employee not found")
            if entity == "department":
                record = str(uuid4())
                self.connection.execute(
                    """INSERT INTO ago_department_lifecycle_events
                       (id,tenant_id,department_id,action,actor_id,approval_id,reason)
                       VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (record, actor.tenant_id, target, change_kind,
                     actor.subject, str(UUID(approval_id)), reason.strip()),
                )
            else:
                last = self.connection.execute(
                    """SELECT role_level FROM ago_personnel_events
                       WHERE tenant_id=%s AND employee_id=%s
                       ORDER BY created_at DESC,id DESC LIMIT 1""",
                    (actor.tenant_id, target),
                ).fetchone()
                previous_level = int(last["role_level"]) if last else 1
                next_level = (role_level if change_kind == "promoted"
                              else (1 if change_kind == "hired" else previous_level))
                if change_kind == "promoted" and (
                    next_level is None or next_level <= previous_level
                ):
                    raise ValueError("Promotion requires strictly higher role level")
                record = str(uuid4())
                self.connection.execute(
                    """INSERT INTO ago_personnel_events
                       (id,tenant_id,employee_id,change_kind,role_level,
                        actor_id,approval_id,reason)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (record, actor.tenant_id, target, change_kind, next_level,
                     actor.subject, str(UUID(approval_id)), reason.strip()),
                )
        return {"id": record, "target_id": target, "change_kind": change_kind,
                "idempotent": False, "independently_approved": True}

    def organization_history(self, *, tenant_id: str) -> dict:
        tenant = str(UUID(tenant_id))
        personnel = [dict(x) for x in self.connection.execute(
            """SELECT id,employee_id,change_kind,role_level,reason,created_at
               FROM ago_personnel_events WHERE tenant_id=%s
               ORDER BY created_at DESC,id DESC LIMIT 100""",
            (tenant,),
        ).fetchall()]
        departments = [dict(x) for x in self.connection.execute(
            """SELECT id,department_id,action,reason,created_at
               FROM ago_department_lifecycle_events WHERE tenant_id=%s
               ORDER BY created_at DESC,id DESC LIMIT 100""",
            (tenant,),
        ).fetchall()]
        return {"personnel": personnel, "departments": departments,
                "historical_records_retained": True}


    def review_evolution(self, *, actor: Principal, observation_id: str,
                         approval_id: str, decision: str, rollback_plan: str,
                         evidence_ref: str) -> dict:
        obs = str(UUID(observation_id))
        if decision not in ("endorsed", "rejected"):
            raise ValueError("Unknown evolution review decision")
        if not 1 <= len(rollback_plan.strip()) <= 3000 or not (
            1 <= len(evidence_ref.strip()) <= 1024
        ):
            raise ValueError("Reviewed rollback and evidence references required")
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, "enterprise:evolution:review:" + obs)
            earlier = self.connection.execute(
                """SELECT id,approval_id,decision,rollback_plan,evidence_ref
                   FROM ago_evolution_review_events WHERE tenant_id=%s AND observation_id=%s""",
                (actor.tenant_id, obs),
            ).fetchone()
            if earlier:
                if (str(earlier["approval_id"]) != str(UUID(approval_id))
                    or earlier["decision"] != decision
                    or earlier["rollback_plan"] != rollback_plan.strip()
                    or earlier["evidence_ref"] != evidence_ref.strip()):
                    raise PermissionError("Cannot rewrite independently reviewed evaluation")
                return {"id": str(earlier["id"]), "decision": decision,
                        "idempotent": True, "applied": False}
            if not self.connection.execute(
                "SELECT 1 FROM ago_evolution_observations WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, obs),
            ).fetchone():
                raise LookupError("Evidence observation absent")
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_evolution_review_events
                   (id,tenant_id,observation_id,actor_id,approval_id,decision,
                    rollback_plan,evidence_ref)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                (identifier, actor.tenant_id, obs, actor.subject,
                 str(UUID(approval_id)), decision, rollback_plan.strip(),
                 evidence_ref.strip()),
            )
        return {"id": identifier, "observation_id": obs,
                "decision": decision, "idempotent": False, "applied": False}

    def evolution_reviews(self, *, tenant_id: str) -> list[dict]:
        return [dict(x) for x in self.connection.execute(
            """SELECT id,observation_id,decision,rollback_plan,evidence_ref,created_at
               FROM ago_evolution_review_events WHERE tenant_id=%s
               ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def compare_twin_outcome(self, *, actor: Principal, scenario_id: str,
                             later_snapshot_id: str, approval_id: str,
                             rationale: str) -> dict:
        scenario, after_id = str(UUID(scenario_id)), str(UUID(later_snapshot_id))
        if not 1 <= len(rationale.strip()) <= 2000:
            raise ValueError("Actual comparison rationale required")
        action = "enterprise:twin:compare:" + scenario + ":" + after_id
        with self.connection.transaction():
            self._tenant_lock(actor.tenant_id)
            self._approval(actor, approval_id, action)
            existing = self.connection.execute(
                """SELECT id,outcome,approval_id,rationale FROM ago_twin_observed_comparisons
                   WHERE tenant_id=%s AND scenario_id=%s AND later_snapshot_id=%s""",
                (actor.tenant_id, scenario, after_id),
            ).fetchone()
            if existing:
                if (str(existing["approval_id"]) != str(UUID(approval_id))
                    or existing["rationale"] != rationale.strip()):
                    raise PermissionError("Cannot change historical observed comparison")
                return {"id": str(existing["id"]), **existing["outcome"],
                        "idempotent": True}
            before = self.connection.execute(
                """SELECT t.id,t.created_at,t.result,s.metrics AS base_metrics
                   FROM ago_twin_scenarios t
                   JOIN ago_executive_snapshots s
                     ON s.tenant_id=t.tenant_id AND s.id=t.snapshot_id
                   WHERE t.tenant_id=%s AND t.id=%s""",
                (actor.tenant_id, scenario),
            ).fetchone()
            later = self.connection.execute(
                """SELECT id,metrics,created_at FROM ago_executive_snapshots
                   WHERE tenant_id=%s AND id=%s""",
                (actor.tenant_id, after_id),
            ).fetchone()
            if not before or not later or later["created_at"] <= before["created_at"]:
                raise ValueError("Later tenant evidence required after scenario capture")
            first = before["base_metrics"].get("completed_tasks")
            last = later["metrics"].get("completed_tasks")
            if type(first) is not int or type(last) is not int or last < first:
                raise ValueError("Valid nondecreasing actual completed task counts required")
            predicted = Decimal(str(before["result"].get("estimated_successful_actions")))
            observed = last - first
            outcome = {
                "calibration": "descriptive_only",
                "predicted_successful_actions": str(predicted),
                "observed_completed_task_delta": observed,
                "absolute_difference": str(abs(predicted - Decimal(observed))),
                "snapshot_comparison": [str(before["id"]), after_id],
                "source": "immutable_executive_snapshots",
                "limits": "Actions and completed tasks are not proven comparable; no accuracy certification.",
                "applied": False,
            }
            identifier = str(uuid4())
            self.connection.execute(
                """INSERT INTO ago_twin_observed_comparisons
                   (id,tenant_id,scenario_id,later_snapshot_id,actor_id,
                    approval_id,outcome,rationale)
                   VALUES (%s,%s,%s,%s,%s,%s,%s::jsonb,%s)""",
                (identifier, actor.tenant_id, scenario, after_id, actor.subject,
                 str(UUID(approval_id)), json.dumps(outcome, sort_keys=True),
                 rationale.strip()),
            )
        return {"id": identifier, "idempotent": False, **outcome}

    def twin_comparisons(self, *, tenant_id: str) -> list[dict]:
        return [dict(x) for x in self.connection.execute(
            """SELECT id,scenario_id,later_snapshot_id,outcome,rationale,created_at
               FROM ago_twin_observed_comparisons WHERE tenant_id=%s
               ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]

    def twin_runs(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            """SELECT id,snapshot_id,assumptions,result,calibrated,data_coverage,
                      source_digest,created_at FROM ago_twin_scenarios
               WHERE tenant_id=%s ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]
