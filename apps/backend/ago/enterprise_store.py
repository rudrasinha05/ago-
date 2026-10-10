"""PostgreSQL application adapter for bounded Sections 21-27 operations.

All writes require signed-session actor at the API boundary. High-impact actions
also require independently decided, exact-action governance approvals. This is
local/tenant-scoped software, not a financial settlement or autonomous authority.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.enterprise_domains import (
    ASSET_TYPES, AssetIdentity, HORIZONS, OperatingMode, WorkCandidate,
    WorkerState, allocate, budget_guard, evaluate_change, operational_load,
    transition_mode, twin_scenario, validate_horizon,
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
            if previous:
                already = self.connection.execute(
                    """SELECT id,mode,sequence FROM ago_oos_mode_events
                       WHERE tenant_id=%s AND approval_id=%s""",
                    (tenant, approval_id)
                ).fetchone()
                if already:
                    return dict(already) | {"idempotent": True}
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
        return {
            "id": employee, "name": row["name"], "kind": row["kind"],
            "department_id": str(row["department_id"]),
            "manager_id": str(row["manager_id"]) if row["manager_id"] else None,
            "current_tasks": current, "future_tasks": future,
            "active_count": active, "queued_count": queued,
            "capacity_units": capacity, "confidence": None, "knowledge_level": None,
            "permission_awareness": "requires_runtime_policy_evaluation",
            "learning_evidence": None, "risk": "unassessed",
            "stress": "operational_load_only", "subjective_consciousness": False,
            "help_needed": "unassessed", "evidence_source": "ago_governed_tasks",
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
        state = self.worker_state(tenant_id=tenant_id, employee_id=employee_id)
        mode = self.effective_mode(tenant_id=tenant_id)["mode"]
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
        items = [WorkCandidate(employee_id, str(row["id"]), 50,
                 available_units, 1, True,
                 row["status"] == "ready" and row["approval_status"] == "approved",
                 WorkerState.AVAILABLE, 0) for row in rows]
        admitted = allocate(items, mode=OperatingMode.ACTIVE) if mode == "active" else ()
        return {"mode": mode, "admitted_task_ids": [x.task_id for x in admitted],
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

    def asset_draft(self, *, actor: Principal, department_id: str, name: str,
                    kind: str, version: str, license_id: str,
                    digest: str, manifest: dict) -> dict:
        identity = AssetIdentity(actor.tenant_id, actor.subject, name, kind,
                                 version, license_id, digest)
        identity.validate()
        if not isinstance(manifest, dict) or len(json.dumps(manifest)) > 16000:
            raise ValueError("Bounded asset manifest required")
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
                """SELECT approval_id,publisher_id,status FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone()
            if not asset:
                raise LookupError("Asset not found")
            if asset["status"] != "proposed" or str(asset["publisher_id"]) != actor.subject:
                raise PermissionError("Only publisher can reconcile proposed asset")
            self._approval(actor, str(asset["approval_id"]),
                           "enterprise:publish:" + asset_id)
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
            if not self.connection.execute(
                """SELECT 1 FROM ago_marketplace_assets
                   WHERE tenant_id=%s AND id=%s AND status='published'""",
                (actor.tenant_id, str(UUID(asset_id))),
            ).fetchone():
                raise PermissionError("Only active tenant-owned published asset may be used")
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
            count = self.connection.execute(
                """SELECT count(*) AS n FROM ago_employees WHERE tenant_id=%s AND kind='ai'""",
                (actor.tenant_id,),
            ).fetchone()["n"]
            model = twin_scenario(
                workers=count, actions=actions, cost_per_action=cost_per_action,
                budget=budget, failure_pct=failure_pct, hiring=hiring, layoffs=layoffs,
                market_shock_pct=market_shock_pct, observed_samples=0,
            )
            model["snapshot_created_at"] = snap["created_at"].isoformat()
            model["observed_workers"] = count
            model["data_coverage"] = "partial"
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

    def twin_runs(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            """SELECT id,snapshot_id,assumptions,result,calibrated,data_coverage,
                      source_digest,created_at FROM ago_twin_scenarios
               WHERE tenant_id=%s ORDER BY created_at DESC,id LIMIT 100""",
            (str(UUID(tenant_id)),),
        ).fetchall()]
