"""Versioned read-only analytical projections, source lineage and reviewed reporting."""

from __future__ import annotations

import math
import statistics
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.reviewed_changes import ReviewedChanges, canonical, digest
from ago.security import Principal
from ago.security_controls import SecurityControls
from ago.graph_store import EnterpriseGraph

DASHBOARDS = (
    "executive",
    "department",
    "employee",
    "finance",
    "workflow",
    "qa",
    "security",
    "architecture",
    "infrastructure",
    "knowledge",
    "memory",
    "innovation",
    "digital_twin",
    "meta_brain",
    "health",
)
# Trusted source-owned table catalog; never interpolated from user requests.
COUNTERS = {
    "departments": "ago_departments",
    "employees": "ago_employees",
    "tasks": "ago_governed_tasks",
    "runs": "ago_agent_runs",
    "qa_reviews": "ago_task_reviews",
    "approvals": "ago_approval_requests",
    "security_events": "ago_security_audit",
    "memory_records": "ago_scoped_memories",
    "graph_versions": "ago_graph_versions",
    "experiments": "ago_policy_experiments",
    "twin_scenarios": "ago_twin_scenarios",
    "recommendations": "ago_meta_recommendations",
    "assets": "ago_marketplace_assets",
    "tool_runs": "ago_tool_runs",
    "calendar_events": "ago_calendar_events",
    "behavior_records": "ago_behavior_records",
}
METRICS = {
    **{
        k: {
            "unit": "records",
            "formula": "count of current tenant source rows",
            "source": v,
            "grain": "tenant",
            "owner": "source context",
            "limitations": "Stock count; not quality, throughput, causality or employee ranking",
        }
        for k, v in COUNTERS.items()
    },
    "qa_pass_rate": {
        "unit": "ratio",
        "formula": "passed QA / total reviewed tasks",
        "source": "ago_task_reviews",
        "grain": "tenant/department/employee",
        "owner": "QA",
        "limitations": "Unknown without reviewed outcomes; pair with risk and task complexity",
    },
    "task_failure_rate": {
        "unit": "ratio",
        "formula": "failed / (completed + failed)",
        "source": "ago_governed_tasks",
        "grain": "tenant/department/employee",
        "owner": "operations",
        "limitations": "Unknown without completed outcomes; task complexity differs",
    },
    "backlog": {
        "unit": "tasks",
        "formula": "proposed + waiting_approval + ready",
        "source": "ago_governed_tasks",
        "grain": "tenant/department/employee",
        "owner": "operations",
        "limitations": "Backlog stock, not delivery failure",
    },
}


def forecast_series(points, horizon_days=7):
    if not 1 <= horizon_days <= 90:
        raise ValueError("Forecast horizon1..90 days required")
    if len(points) < 5:
        return {"status": "insufficient_evidence", "minimum_points": 5, "prediction": None}
    ordered = sorted(points, key=lambda p: p[0])
    origin = ordered[0][0]
    xs = [(p[0] - origin).total_seconds() / 86400 for p in ordered]
    ys = [float(p[1]) for p in ordered]
    if any(not math.isfinite(y) for y in ys) or xs[-1] - xs[0] < 1:
        return {"status": "insufficient_time_span", "prediction": None}
    mx = statistics.mean(xs)
    my = statistics.mean(ys)
    ss = sum((x - mx) ** 2 for x in xs)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / ss
    intercept = my - slope * mx
    residuals = [y - (intercept + slope * x) for x, y in zip(xs, ys)]
    variance = sum(r * r for r in residuals) / (len(xs) - 2)
    target = xs[-1] + horizon_days
    prediction = intercept + slope * target
    width = 3.182 * math.sqrt(variance * (1 + 1 / len(xs) + (target - mx) ** 2 / ss))
    return {
        "status": "estimated",
        "prediction": prediction,
        "interval_95_approx": [prediction - width, prediction + width],
        "slope_per_day": slope,
        "n": len(xs),
        "residual_rmse": math.sqrt(variance),
        "horizon_days": horizon_days,
        "assumptions": [
            "Linear local trend",
            "Independent comparable observations",
            "No causal inference",
        ],
        "limitations": [
            "Small-sample approximate interval",
            "Not validated against future outcomes",
        ],
        "observed_until": ordered[-1][0].isoformat(),
    }


def anomaly(values, current):
    if len(values) < 5:
        return {"status": "insufficient_evidence", "flagged": False}
    center = statistics.median(values)
    mad = statistics.median(abs(x - center) for x in values)
    deviation = abs(current - center)
    flagged = deviation > max(3 * 1.4826 * mad, abs(center) * 0.2, 1e-9)
    return {
        "status": "evaluated",
        "flagged": flagged,
        "baseline_median": center,
        "median_absolute_deviation": mad,
        "method": "robust median/MAD with20% relative floor",
        "causal_claim": False,
    }


class AnalyticsStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _read(self, actor):
        if not self.repositories.resolve(SecurityControls).permitted(
            actor, "insights:read", actor.tenant_id
        ):
            raise PermissionError("Analytics read authority required")

    def catalog(self, *, actor: Principal) -> dict:
        self._read(actor)
        definitions = [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM ago_analytics_settings WHERE tenant_id=%s AND kind='metric' ORDER BY revision",
                (actor.tenant_id,),
            ).fetchall()
        ]
        return {
            "schema_version": 1,
            "dashboards": list(DASHBOARDS),
            "metrics": METRICS,
            "reviewed_definitions": definitions,
        }

    def dashboard(
        self,
        *,
        actor: Principal,
        dashboard: str = "executive",
        department_id: str | None = None,
        employee_id: str | None = None,
    ) -> dict:
        self._read(actor)
        if dashboard not in DASHBOARDS:
            raise ValueError("Unknown dashboard")
        for value, table in [(department_id, "ago_departments"), (employee_id, "ago_employees")]:
            if value:
                UUID(value)
                if not self.db.execute(
                    f"SELECT 1 FROM {table} WHERE tenant_id=%s AND id=%s", (actor.tenant_id, value)
                ).fetchone():
                    raise LookupError("Same-tenant analytics scope required")
        if (
            dashboard == "employee"
            and not employee_id
            or dashboard == "department"
            and not department_id
        ):
            raise ValueError("Explicit dashboard scope required")
        counts = {}
        for name, table in COUNTERS.items():
            counts[name] = self.db.execute(
                f"SELECT count(*) n FROM {table} WHERE tenant_id=%s", (actor.tenant_id,)
            ).fetchone()["n"]
        tasks = self.db.execute(
            """SELECT t.status,count(*) n FROM ago_governed_tasks t JOIN ago_employees e
            ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id WHERE t.tenant_id=%s
            AND (%s::uuid IS NULL OR e.department_id=%s) AND (%s::uuid IS NULL OR e.id=%s) GROUP BY t.status""",
            (actor.tenant_id, department_id, department_id, employee_id, employee_id),
        ).fetchall()
        statuses = {r["status"]: r["n"] for r in tasks}
        qa = self.db.execute(
            """SELECT q.verdict,count(*) n FROM ago_task_reviews q JOIN ago_governed_tasks t
            ON t.tenant_id=q.tenant_id AND t.id=q.task_id JOIN ago_employees e ON e.tenant_id=t.tenant_id AND e.id=t.assignee_id
            WHERE q.tenant_id=%s AND (%s::uuid IS NULL OR e.department_id=%s) AND (%s::uuid IS NULL OR e.id=%s) GROUP BY q.verdict""",
            (actor.tenant_id, department_id, department_id, employee_id, employee_id),
        ).fetchall()
        q = {r["verdict"]: r["n"] for r in qa}
        total = sum(q.values())
        finished = statuses.get("completed", 0) + statuses.get("failed", 0)
        measures = {
            **counts,
            "qa_pass_rate": q.get("pass", 0) / total if total else None,
            "task_failure_rate": statuses.get("failed", 0) / finished if finished else None,
            "backlog": sum(statuses.get(k, 0) for k in ("proposed", "waiting_approval", "ready")),
        }
        costs = [
            dict(r)
            for r in self.db.execute(
                """SELECT category,currency,count(*) records,sum(observed_amount) amount
            FROM ago_observed_costs WHERE tenant_id=%s GROUP BY category,currency ORDER BY currency,category""",
                (actor.tenant_id,),
            ).fetchall()
        ]
        audit = [
            dict(r)
            for r in self.db.execute(
                "SELECT action,outcome,count(*) records FROM ago_security_audit WHERE tenant_id=%s GROUP BY action,outcome ORDER BY records DESC LIMIT 30",
                (actor.tenant_id,),
            ).fetchall()
        ]
        recent = [
            dict(r)
            for r in self.db.execute(
                "SELECT id,kind,digest,created_at FROM ago_enterprise_evidence WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 30",
                (actor.tenant_id,),
            ).fetchall()
        ]
        graph = self.db.execute(
            "SELECT count(DISTINCT entity_id) n FROM ago_graph_versions WHERE tenant_id=%s",
            (actor.tenant_id,),
        ).fetchone()["n"]
        missing = {
            "architecture": ["runtime deployment topology", "technical debt evaluation"],
            "infrastructure": ["host resource telemetry", "latency series", "throughput telemetry"],
            "memory": ["human-rated retrieval relevance"],
            "innovation": ["validated market value"],
            "finance": ["authenticated provider invoices", "real realized ROI"],
            "health": ["validated workload limits", "human wellbeing measurements"],
            "digital_twin": ["prospective observed forecast outcomes"],
        }.get(dashboard, [])
        views = {
            "executive": list(measures),
            "department": ["backlog", "qa_pass_rate", "task_failure_rate"],
            "employee": ["backlog", "qa_pass_rate", "task_failure_rate"],
            "finance": ["tasks", "tool_runs"],
            "workflow": ["tasks", "runs", "backlog", "approvals", "task_failure_rate"],
            "qa": ["qa_reviews", "qa_pass_rate", "task_failure_rate"],
            "security": ["security_events", "tool_runs"],
            "architecture": ["assets", "experiments"],
            "infrastructure": ["runs", "tool_runs", "backlog"],
            "knowledge": ["graph_versions"],
            "memory": ["memory_records"],
            "innovation": ["experiments", "assets"],
            "digital_twin": ["twin_scenarios"],
            "meta_brain": ["recommendations"],
            "health": ["employees", "departments", "backlog", "qa_pass_rate", "behavior_records"],
        }
        details = {}
        if dashboard in ("workflow", "infrastructure", "health"):
            details["task_age"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT status,count(*) records,avg(extract(epoch FROM (clock_timestamp()-created_at))) mean_age_seconds,max(extract(epoch FROM (clock_timestamp()-created_at))) oldest_age_seconds FROM ago_governed_tasks WHERE tenant_id=%s GROUP BY status",
                    (actor.tenant_id,),
                ).fetchall()
            ]
            details["workload"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT assignee_id,count(*) open_tasks FROM ago_governed_tasks WHERE tenant_id=%s AND status NOT IN ('completed','failed') GROUP BY assignee_id ORDER BY open_tasks DESC LIMIT 100",
                    (actor.tenant_id,),
                ).fetchall()
            ]
            details["interpretation"] = (
                "Age since creation; not execution latency. Workload count is not employee health."
            )
        if dashboard == "memory":
            details["company_memory"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT state,kind,count(*) records FROM ago_scoped_memories WHERE tenant_id=%s AND scope='company' GROUP BY state,kind",
                    (actor.tenant_id,),
                ).fetchall()
            ]
            details["private_content_returned"] = False
        if dashboard == "knowledge":
            details["graph_quality"] = self.repositories.resolve(EnterpriseGraph).quality(
                actor=actor
            )
        if dashboard == "finance":
            details["budget_envelopes"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT scope_kind,currency,count(*) envelopes,sum(approved_ceiling) ceiling FROM ago_budget_envelopes WHERE tenant_id=%s GROUP BY scope_kind,currency",
                    (actor.tenant_id,),
                ).fetchall()
            ]
            details["cost_evidence"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT evidence_state,currency,count(*) records,sum(observed_amount) amount FROM ago_observed_costs WHERE tenant_id=%s GROUP BY evidence_state,currency",
                    (actor.tenant_id,),
                ).fetchall()
            ]
        if dashboard == "digital_twin":
            details["coverage"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT data_coverage,calibrated,count(*) scenarios FROM ago_twin_scenarios WHERE tenant_id=%s GROUP BY data_coverage,calibrated",
                    (actor.tenant_id,),
                ).fetchall()
            ]
        if dashboard == "meta_brain":
            details["recommendations"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT category,status,count(*) records FROM ago_meta_recommendations WHERE tenant_id=%s GROUP BY category,status",
                    (actor.tenant_id,),
                ).fetchall()
            ]
        if dashboard == "innovation":
            details["review_states"] = [
                dict(r)
                for r in self.db.execute(
                    "SELECT coalesce(a.status,'unsubmitted') status,count(*) experiments FROM ago_policy_experiments e LEFT JOIN ago_approval_requests a ON a.tenant_id=e.tenant_id AND a.id=e.approval_id WHERE e.tenant_id=%s GROUP BY a.status",
                    (actor.tenant_id,),
                ).fetchall()
            ]
        if dashboard == "architecture":
            from ago.architecture_guard import verify

            details["source_architecture"] = verify().as_dict()
            details["scope"] = (
                "Packaged Python dependency rules; not runtime infrastructure telemetry"
            )
        return {
            "details": details,
            "dashboard": dashboard,
            "scope": {"department_id": department_id, "employee_id": employee_id},
            "observed_at": datetime.now(timezone.utc).isoformat(),
            "definition_version": 1,
            "metrics": {k: {"value": measures[k], **METRICS[k]} for k in views[dashboard]},
            "task_status": statuses,
            "qa_status": q,
            "costs": costs if dashboard in ("finance", "executive") else [],
            "cost_status": "Recorded claims; independent reconciliation must be inspected before calling these actual expenses",
            "security_summary": audit if dashboard in ("security", "executive") else [],
            "evidence_lineage": recent,
            "graph_entities": graph,
            "missing_measurements": missing,
            "limitations": [
                "Tenant stock counters are explicitly tenant-wide",
                "Task and QA measures use requested scope",
                "No employee ranking; task complexity and risk need controlled comparisons",
            ],
        }

    def capture(self, *, actor: Principal, operation_key: str) -> dict:
        self._read(actor)
        if not 1 <= len(operation_key) <= 160:
            raise ValueError("Snapshot operation key required")
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            existing = self.db.execute(
                "SELECT * FROM ago_analytics_snapshots WHERE tenant_id=%s AND operation_key=%s",
                (actor.tenant_id, operation_key),
            ).fetchone()
            if existing:
                return dict(existing)
            projection = self.dashboard(actor=actor)
            return dict(
                self.db.execute(
                    """INSERT INTO ago_analytics_snapshots(id,tenant_id,actor_id,operation_key,projection,digest)
                VALUES(%s,%s,%s,%s,%s::jsonb,%s) RETURNING *""",
                    (
                        str(uuid4()),
                        actor.tenant_id,
                        actor.subject,
                        operation_key,
                        canonical(projection),
                        digest(projection),
                    ),
                ).fetchone()
            )

    def history(self, *, actor: Principal, metric: str, horizon_days: int = 7) -> dict:
        self._read(actor)
        if metric not in METRICS:
            raise ValueError("Versioned metric required")
        rows = self.db.execute(
            "SELECT id,projection,created_at FROM ago_analytics_snapshots WHERE tenant_id=%s ORDER BY created_at DESC,id LIMIT 90",
            (actor.tenant_id,),
        ).fetchall()[::-1]
        points = [
            (r["created_at"], r["projection"]["metrics"][metric]["value"])
            for r in rows
            if r["projection"]["metrics"].get(metric, {}).get("value") is not None
        ]
        result = forecast_series(points, horizon_days)
        if points:
            result["stale"] = (datetime.now(timezone.utc) - points[-1][0]) > timedelta(days=7)
        return {
            "metric": metric,
            "definition": METRICS[metric],
            "source_snapshot_ids": [str(r["id"]) for r in rows],
            "forecast": result,
            "anomaly": anomaly([p[1] for p in points[:-1]], points[-1][1])
            if points
            else {"status": "insufficient_evidence", "flagged": False},
        }

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
        if command == "metric":
            if (
                set(specification) != {"id", "metric", "owner", "purpose", "limitations", "version"}
                or specification["metric"] not in METRICS
            ):
                raise ValueError("Reviewed existing formula and definition metadata required")
            if type(specification["version"]) is not int or specification["version"] < 1:
                raise ValueError("Definition version required")
            for k in ("owner", "purpose", "limitations"):
                if not isinstance(specification[k], str) or not 1 <= len(specification[k]) <= 3000:
                    raise ValueError("Substantive metric metadata required")
        elif command == "schedule":
            if (
                set(specification) != {"id", "report", "cadence", "enabled"}
                or specification["report"] not in set(DASHBOARDS) - {"department", "employee"}
                or specification["cadence"] not in ("weekly", "monthly", "quarterly", "annual")
                or type(specification["enabled"]) is not bool
            ):
                raise ValueError("Bounded report schedule required")
        else:
            raise ValueError("Unknown analytics command")
        UUID(specification["id"])
        return self.repositories.resolve(ReviewedChanges).propose(
            actor=actor,
            domain="analytics",
            command=command,
            specification=specification,
            source={"formula_catalog_digest": digest(METRICS)},
            operation_key=operation_key,
            base_revision=base_revision,
            rationale=rationale,
        )

    def apply(self, *, actor: Principal, proposal_id: str) -> dict:
        ledger = self.repositories.resolve(ReviewedChanges)
        with self.db.transaction():
            p = ledger.package(actor=actor, proposal_id=proposal_id, domain="analytics")
            if p.get("applied"):
                return p["applied"]
            if p["source"]["formula_catalog_digest"] != digest(METRICS):
                raise PermissionError("Metric definition changed since review")
            self.db.execute(
                "INSERT INTO ago_analytics_settings(tenant_id,id,revision,kind,payload,proposal_id) VALUES(%s,%s,%s,%s,%s::jsonb,%s)",
                (
                    actor.tenant_id,
                    p["specification"]["id"],
                    p["base_revision"] + 1,
                    p["command"],
                    canonical(p["specification"]),
                    p["id"],
                ),
            )
            return ledger.finish(
                actor=actor,
                package=p,
                result={"id": p["specification"]["id"], "kind": p["command"]},
            )

    def reports(self, *, actor: Principal) -> list[dict]:
        self._read(actor)
        return [
            dict(r)
            for r in self.db.execute(
                "SELECT * FROM ago_analytics_reports WHERE tenant_id=%s ORDER BY created_at DESC LIMIT 100",
                (actor.tenant_id,),
            ).fetchall()
        ]

    def tick(self, *, actor: Principal) -> dict:
        self.repositories.resolve(ReviewedChanges).require(actor, "analytics")
        now = datetime.now(timezone.utc)
        created = []
        schedules = self.db.execute(
            "SELECT DISTINCT ON(id) * FROM ago_analytics_settings WHERE tenant_id=%s AND kind='schedule' ORDER BY id,revision DESC",
            (actor.tenant_id,),
        ).fetchall()
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (actor.tenant_id,))
            for row in schedules:
                p = row["payload"]
                if not p["enabled"]:
                    continue
                cadence = p["cadence"]
                period = (
                    now.strftime("%G-W%V")
                    if cadence == "weekly"
                    else now.strftime("%Y-%m")
                    if cadence == "monthly"
                    else f"{now.year}-Q{(now.month - 1) // 3 + 1}"
                    if cadence == "quarterly"
                    else str(now.year)
                )
                if self.db.execute(
                    "SELECT 1 FROM ago_analytics_reports WHERE tenant_id=%s AND schedule_id=%s AND period=%s",
                    (actor.tenant_id, row["id"], period),
                ).fetchone():
                    continue
                view = p["report"]
                report = self.dashboard(actor=actor, dashboard=view)
                alerts = []
                for metric in ("backlog", "qa_pass_rate", "task_failure_rate", "security_events"):
                    signal = self.history(actor=actor, metric=metric)
                    if signal["anomaly"]["flagged"]:
                        alerts.append(
                            {
                                "metric": metric,
                                "owner": "security"
                                if metric == "security_events"
                                else "human leadership",
                                "signal": signal,
                            }
                        )
                identifier = str(uuid4())
                self.db.execute(
                    """INSERT INTO ago_analytics_reports(id,tenant_id,schedule_id,period,report,alerts)
                    VALUES(%s,%s,%s,%s,%s::jsonb,%s::jsonb)""",
                    (
                        identifier,
                        actor.tenant_id,
                        row["id"],
                        period,
                        canonical(report),
                        canonical(alerts),
                    ),
                )
                created.append(identifier)
        return {"created_report_ids": created, "external_messages_sent": 0}
