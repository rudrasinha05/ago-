"""M2 governance: action policy and transactional PostgreSQL approvals.

Authorization of reviewers and execution must be enforced by the caller using
trusted, authenticated principals; never accept actor identity from untrusted input.
"""

from __future__ import annotations

from uuid import UUID

from ago.approvals import ApprovalRequest, ApprovalStatus
from ago.security import Principal
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance_domain import Constitution as Constitution
from ago.governance_domain import Decision as Decision
from ago.governance_domain import Risk as Risk


class ApprovalRepository:
    """Transactions guarantee a single terminal decision and matching audit entry.

    Expects a psycopg connection with dict_row row factory and autocommit=False.
    """

    def __init__(
        self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None
    ):
        self.connection = connection
        self.repositories = repositories or RepositoryScope(connection)

    def propose(self, *, tenant_id: str, action: str, requester_id: str) -> ApprovalRequest:
        proposal = ApprovalRequest.propose(
            tenant_id=tenant_id, action=action, requester_id=requester_id
        )
        # Validate identifiers before executing SQL.
        for value in (tenant_id, requester_id):
            UUID(value)
        with self.connection.transaction():
            self.connection.execute(
                """INSERT INTO ago_approval_requests
                   (id, tenant_id, action, requester_id) VALUES (%s, %s, %s, %s)""",
                (proposal.request_id, tenant_id, action, requester_id),
            )
            self.connection.execute(
                """INSERT INTO ago_approval_audit
                   (request_id, tenant_id, actor_id, event)
                   VALUES (%s, %s, %s, 'proposed')""",
                (proposal.request_id, tenant_id, requester_id),
            )
        return proposal

    def decide(
        self,
        *,
        request_id: str,
        tenant_id: str,
        reviewer_id: str,
        approve: bool,
        reason: str,
        authorized: bool = False,
    ) -> ApprovalRequest:
        if not authorized:
            raise PermissionError("Authenticated founder authorization required")
        for value in (request_id, tenant_id, reviewer_id):
            UUID(value)
        with self.connection.transaction():
            row = self.connection.execute(
                """SELECT id, tenant_id, action, requester_id, status,
                          reviewer_id, reason
                   FROM ago_approval_requests WHERE id=%s AND tenant_id=%s
                   FOR UPDATE""",
                (request_id, tenant_id),
            ).fetchone()
            if row is None:
                raise LookupError("Approval not found")
            current = ApprovalRequest(
                request_id=str(row["id"]),
                tenant_id=str(row["tenant_id"]),
                action=row["action"],
                requester_id=str(row["requester_id"]),
                status=ApprovalStatus(row["status"]),
                reviewer_id=str(row["reviewer_id"]) if row["reviewer_id"] else None,
                reason=row["reason"],
            )
            human = self.connection.execute(
                """SELECT 1 FROM ago_users u JOIN ago_employees e
                     ON e.id=u.id AND e.tenant_id=u.tenant_id
                   WHERE u.id=%s AND u.tenant_id=%s AND u.active=true
                     AND e.kind='human'""",
                (reviewer_id, tenant_id),
            ).fetchone()
            if human is None:
                raise PermissionError("Active human decision-maker required")
            founder = self.connection.execute(
                """SELECT 1 FROM ago_users u
                     JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
                     JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
                   WHERE u.id=%s AND u.tenant_id=%s AND u.active
                     AND e.kind='human' AND r.role='founder'""",
                (reviewer_id, tenant_id),
            ).fetchone()
            active_founder_exists = self.connection.execute(
                """SELECT 1 FROM ago_users u
                     JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
                     JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
                   WHERE u.tenant_id=%s AND u.active AND e.kind='human'
                     AND r.role='founder' LIMIT 1""",
                (tenant_id,),
            ).fetchone()
            if founder is None:
                raise PermissionError("Only the active human founder may approve or deny")
            # Legacy standalone test tenants have no founder role; preserve
            # their independently reviewed historical flows without granting
            # the founder role to fictitious or automated employees.
            decided = current.decide(
                reviewer_id=reviewer_id,
                tenant_id=tenant_id,
                approve=approve,
                reason=reason,
                founder_authorized=founder is not None,
            )
            self.connection.execute(
                """UPDATE ago_approval_requests
                   SET status=%s, reviewer_id=%s, reason=%s, decided_at=now()
                   WHERE id=%s AND tenant_id=%s AND status='pending'""",
                (decided.status.value, reviewer_id, decided.reason, request_id, tenant_id),
            )
            self.connection.execute(
                """INSERT INTO ago_approval_audit
                   (request_id, tenant_id, actor_id, event, reason)
                   VALUES (%s, %s, %s, %s, %s)""",
                (request_id, tenant_id, reviewer_id, decided.status.value, decided.reason),
            )
        return decided

    def list_requests(self, *, tenant_id: str, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid approval list limit")
        rows = self.connection.execute(
            """SELECT id, action, requester_id, reviewer_id, status, reason, created_at
               FROM ago_approval_requests WHERE tenant_id=%s
               ORDER BY created_at DESC, id LIMIT %s""",
            (tenant_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def assert_executable(self, *, request_id: str, tenant_id: str, action: str) -> None:
        row = self.connection.execute(
            """SELECT action, status FROM ago_approval_requests
               WHERE id=%s AND tenant_id=%s""",
            (request_id, tenant_id),
        ).fetchone()
        if row is None or row["action"] != action or row["status"] != "approved":
            raise PermissionError("Approved action not found for tenant and scope")

    def propose_architecture(self, *, tenant_id: str, requester_id: str,
                             change_key: str, specification: dict) -> dict:
        from uuid import uuid4
        from ago.governance_domain import validate_architecture_change

        specification = validate_architecture_change(change_key, specification)
        identifier = str(uuid4())
        with self.connection.transaction():
            tenant = self.connection.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE", (str(UUID(tenant_id)),),
            ).fetchone()
            if tenant is None:
                raise LookupError("Tenant not found")
            if self.connection.execute(
                "SELECT id FROM ago_architecture_changes WHERE tenant_id=%s AND change_key=%s",
                (tenant_id, change_key),
            ).fetchone() is not None:
                raise ValueError("Architecture change key already exists; use a new versioned record")
            approval = self.propose(tenant_id=tenant_id, requester_id=requester_id,
                                    action=f"architecture:review:{identifier}")
            import json
            self.connection.execute(
                """INSERT INTO ago_architecture_changes
                   (id,tenant_id,proposer_id,approval_id,change_key,specification)
                   VALUES (%s,%s,%s,%s,%s,%s::jsonb)""",
                (identifier, tenant_id, requester_id, approval.request_id,
                 change_key, json.dumps(specification, sort_keys=True)),
            )
        return {"id": identifier, "approval_id": approval.request_id,
                "status": "proposed", "applied": False}

    def architecture_changes(self, *, tenant_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            """SELECT id,change_key,specification,approval_id,status,created_at,decided_at
               FROM ago_architecture_changes WHERE tenant_id=%s
               ORDER BY created_at DESC,id LIMIT 100""", (str(UUID(tenant_id)),),
        ).fetchall()]

    def reconcile_architecture(self, *, tenant_id: str, change_id: str) -> dict:
        with self.connection.transaction():
            row = self.connection.execute(
                """SELECT status,approval_id FROM ago_architecture_changes
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (str(UUID(tenant_id)), str(UUID(change_id))),
            ).fetchone()
            if row is None:
                raise LookupError("Architecture change not found")
            if row["status"] != "proposed":
                raise PermissionError("Change already finalized")
            decision = self.connection.execute(
                "SELECT status,action FROM ago_approval_requests WHERE tenant_id=%s AND id=%s",
                (tenant_id, row["approval_id"]),
            ).fetchone()
            if decision is None or decision["action"] != f"architecture:review:{change_id}":
                raise PermissionError("Exact architecture review required")
            states = {"approved": "accepted", "rejected": "rejected"}
            if decision["status"] not in states:
                raise PermissionError("Independent review is pending")
            state = states[decision["status"]]
            self.connection.execute(
                """UPDATE ago_architecture_changes SET status=%s,decided_at=clock_timestamp()
                   WHERE tenant_id=%s AND id=%s""", (state, tenant_id, change_id),
            )
        return {"id": change_id, "status": state, "applied": False}

    def _constitutional_founder(self, actor) -> None:
        if not self.connection.execute(
            """SELECT 1 FROM ago_users u JOIN ago_employees e
                 ON e.id=u.id AND e.tenant_id=u.tenant_id
               JOIN ago_user_roles r ON r.user_id=u.id AND r.tenant_id=u.tenant_id
               WHERE u.id=%s AND u.tenant_id=%s AND u.active=true
                 AND e.kind='human' AND r.role='founder'""",
            (actor.subject, actor.tenant_id),
        ).fetchone():
            raise PermissionError("Active human founder required for constitutional authority")

    def constitution_state(self, *, tenant_id: str) -> dict:
        from ago.governance_domain import CONSTITUTION_LAWS, CONSTITUTION_REVIEWS
        tenant = str(UUID(tenant_id))
        proposals = [dict(r) for r in self.connection.execute(
            """SELECT p.*,a.revision,a.effective_at AS adopted_effective_at
               FROM ago_constitution_proposals p LEFT JOIN ago_constitution_adoptions a
                 ON a.tenant_id=p.tenant_id AND a.proposal_id=p.id
               WHERE p.tenant_id=%s ORDER BY p.created_at DESC,p.id LIMIT 100""", (tenant,),
        ).fetchall()]
        active = self.connection.execute(
            """SELECT revision,proposal_id,blocked_contexts,effective_at FROM ago_constitution_adoptions
               WHERE tenant_id=%s AND effective_at<=clock_timestamp()
               ORDER BY revision DESC LIMIT 1""", (tenant,),
        ).fetchone()
        emergencies = [dict(r) for r in self.connection.execute(
            """SELECT e.*,c.created_at AS closed_at,c.review_id,
                      e.expires_at>clock_timestamp() AND c.emergency_id IS NULL AS active,
                      c.emergency_id IS NULL AS retrospective_review_pending
               FROM ago_constitution_emergencies e LEFT JOIN ago_constitution_emergency_closures c
                 ON c.tenant_id=e.tenant_id AND c.emergency_id=e.id
               WHERE e.tenant_id=%s ORDER BY e.created_at DESC,e.id LIMIT 100""", (tenant,),
        ).fetchall()]
        reviews = [dict(r) for r in self.connection.execute(
            """SELECT r.*,a.status,a.reviewer_id,a.reason FROM ago_constitution_emergency_reviews r
               JOIN ago_approval_requests a ON a.tenant_id=r.tenant_id AND a.id=r.approval_id
               WHERE r.tenant_id=%s ORDER BY r.created_at DESC,r.id LIMIT 100""", (tenant,),
        ).fetchall()]
        return {"laws": CONSTITUTION_LAWS, "priority": "above_DNA_and_all_business_subsystems",
                "active": dict(active) if active else {"revision": 0, "blocked_contexts": [], "source": "immutable_baseline"},
                "proposals": proposals, "emergencies": emergencies, "emergency_reviews": reviews,
                "review_domains": CONSTITUTION_REVIEWS, "human_authority": True,
                "review_board": "founder plus independently deciding active human reviewers; five explicit review domains",
                "legal_certification": False, "authority_expansion": False}

    def constitution_command(self, *, actor: Principal, command: str, data: dict) -> dict:
        """Serialized version adoption and reversible, independently reviewed containment."""
        import json
        from datetime import datetime, timedelta, timezone
        from hashlib import sha256
        from uuid import uuid4
        from ago.governance_domain import CONSTITUTION_CONTEXTS, CONSTITUTION_REVIEWS, validate_constitution

        self._constitutional_founder(actor)
        tenant = str(UUID(actor.tenant_id))
        def encoded(value):
            return json.dumps(value, sort_keys=True, default=str, allow_nan=False)
        def digest(value):
            return sha256(encoded(value).encode()).hexdigest()
        def bounded(value):
            if not isinstance(value, str) or not 1 <= len(value.strip()) <= 3000:
                raise ValueError("Bounded substantive constitutional evidence required")
            return value.strip()
        with self.connection.transaction():
            if not self.connection.execute("SELECT 1 FROM ago_tenants WHERE id=%s FOR UPDATE", (tenant,)).fetchone():
                raise LookupError("Organization not found")
            now = self.connection.execute("SELECT clock_timestamp() AS current_time").fetchone()["current_time"]
            if command == "propose":
                specification = validate_constitution(data["specification"])
                effective = datetime.fromisoformat(data["effective_at"])
                if effective.tzinfo is None or not now-timedelta(minutes=5) <= effective <= now+timedelta(days=7):
                    raise ValueError("Timezone-aware requested effective date near present or within seven days required")
                key = bounded(data["operation_key"])
                if len(key)>160:
                    raise ValueError("Bounded operation key required")
                simulation = self.connection.execute(
                    """SELECT id,snapshot_id,source_digest,assumptions,result,data_coverage,calibrated
                       FROM ago_twin_scenarios WHERE tenant_id=%s AND id=%s""",
                    (tenant, specification["simulation_id"]),
                ).fetchone()
                if not simulation:
                    raise LookupError("Actual tenant Twin simulation required")
                payload = {"specification": specification, "simulation": dict(simulation),
                           "base_revision": data["base_revision"], "effective_at": effective.astimezone(timezone.utc).isoformat()}
                signature = digest(payload)
                prior = self.connection.execute(
                    "SELECT id,digest,reviews,actor_id FROM ago_constitution_proposals WHERE tenant_id=%s AND operation_key=%s", (tenant,key),
                ).fetchone()
                if prior:
                    if prior["digest"] != signature or str(prior["actor_id"])!=actor.subject:
                        raise PermissionError("Changed immutable constitutional retry denied")
                    return {**dict(prior), "idempotent": True}
                latest = self.connection.execute(
                    "SELECT coalesce(max(revision),0) AS revision FROM ago_constitution_adoptions WHERE tenant_id=%s", (tenant,),
                ).fetchone()["revision"]
                if type(data["base_revision"]) is not int or data["base_revision"] != latest:
                    raise PermissionError("Stale constitutional base revision")
                identifier = str(uuid4())
                reviews = {domain: self.propose(tenant_id=tenant, requester_id=actor.subject,
                           action=f"constitution:review:{identifier}:{domain}:{signature}").request_id
                           for domain in CONSTITUTION_REVIEWS}
                self.connection.execute(
                    """INSERT INTO ago_constitution_proposals
                       (id,tenant_id,actor_id,operation_key,base_revision,specification,simulation,digest,effective_at,reviews)
                       VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s::jsonb)""",
                    (identifier,tenant,actor.subject,key,latest,encoded(specification),encoded(dict(simulation)),signature,effective,encoded(reviews)),
                )
                return {"id":identifier,"digest":signature,"reviews":reviews,"idempotent":False,"applied":False}
            if command == "adopt":
                item = self.connection.execute(
                    "SELECT * FROM ago_constitution_proposals WHERE tenant_id=%s AND id=%s", (tenant,str(UUID(data["proposal_id"]))),
                ).fetchone()
                if not item:
                    raise LookupError("Constitutional proposal not found")
                if str(item["actor_id"]) != actor.subject:
                    raise PermissionError("Original human founder must adopt the exact reviewed package")
                prior = self.connection.execute(
                    "SELECT revision,effective_at FROM ago_constitution_adoptions WHERE tenant_id=%s AND proposal_id=%s", (tenant,item["id"]),
                ).fetchone()
                if prior:
                    return {**dict(prior),"idempotent":True,"proposal_id":str(item["id"])}
                latest = self.connection.execute(
                    "SELECT revision,effective_at FROM ago_constitution_adoptions WHERE tenant_id=%s ORDER BY revision DESC LIMIT 1", (tenant,),
                ).fetchone()
                if item["base_revision"] != (latest["revision"] if latest else 0) or (latest and latest["effective_at"]>now):
                    raise PermissionError("Stale revision or previously scheduled constitution; review a new package")
                for domain, approval in item["reviews"].items():
                    row = self.connection.execute(
                        """SELECT a.status,a.requester_id,a.reviewer_id,a.action FROM ago_approval_requests a
                           JOIN ago_users u ON u.id=a.reviewer_id AND u.tenant_id=a.tenant_id
                           JOIN ago_employees e ON e.id=u.id AND e.tenant_id=u.tenant_id
                           WHERE a.tenant_id=%s AND a.id=%s AND u.active AND e.kind='human'""", (tenant,approval),
                    ).fetchone()
                    if (not row or row["status"]!="approved" or str(row["requester_id"])!=actor.subject
                            or str(row["reviewer_id"])==actor.subject
                            or row["action"]!=f"constitution:review:{item['id']}:{domain}:{item['digest']}"):
                        raise PermissionError("Five-domain independent human review required")
                effective = max(item["effective_at"],now)
                revision = item["base_revision"]+1
                self.connection.execute(
                    """INSERT INTO ago_constitution_adoptions
                       (id,tenant_id,proposal_id,actor_id,revision,blocked_contexts,effective_at)
                       VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                    (str(uuid4()),tenant,item["id"],actor.subject,revision,item["specification"]["blocked_contexts"],effective),
                )
                return {"proposal_id":str(item["id"]),"revision":revision,"effective_at":effective,"idempotent":False}
            if command == "emergency":
                key = bounded(data["operation_key"])
                reason, containment = bounded(data["reason"]), bounded(data["containment"])
                expiry = datetime.fromisoformat(data["expires_at"])
                contexts = data["blocked_contexts"]
                if (len(key)>160 or not isinstance(contexts,list) or not contexts
                        or any(not isinstance(x,str) or x not in CONSTITUTION_CONTEXTS for x in contexts) or len(contexts)!=len(set(contexts))):
                    raise ValueError("Explicit bounded containment contexts required")
                if expiry.tzinfo is None or not now<expiry<=now+timedelta(hours=24):
                    raise ValueError("Emergency must expire within 24 hours")
                signature = digest({"blocked_contexts":contexts,"reason":reason,"containment":containment,
                                    "expires_at":expiry.astimezone(timezone.utc).isoformat()})
                prior = self.connection.execute(
                    "SELECT id,digest,actor_id FROM ago_constitution_emergencies WHERE tenant_id=%s AND operation_key=%s",(tenant,key),
                ).fetchone()
                if prior:
                    if prior["digest"]!=signature or str(prior["actor_id"])!=actor.subject:
                        raise PermissionError("Emergency retry cannot extend or alter containment")
                    return {**dict(prior),"idempotent":True}
                if self.connection.execute(
                    """SELECT 1 FROM ago_constitution_emergencies e WHERE e.tenant_id=%s
                       AND NOT EXISTS(SELECT 1 FROM ago_constitution_emergency_closures c
                         WHERE c.tenant_id=e.tenant_id AND c.emergency_id=e.id)""",(tenant,),
                ).fetchone():
                    raise PermissionError("Prior incident must receive retrospective review before another declaration")
                identifier = str(uuid4())
                self.connection.execute(
                    """INSERT INTO ago_constitution_emergencies
                       (id,tenant_id,actor_id,operation_key,blocked_contexts,reason,containment,expires_at,digest)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (identifier,tenant,actor.subject,key,contexts,reason,containment,expiry,signature),
                )
                return {"id":identifier,"expires_at":expiry,"blocked_contexts":contexts,"idempotent":False,
                        "authority_expansion":False,"retrospective_review_required":True}
            if command == "incident-review":
                incident = self.connection.execute(
                    "SELECT id,digest FROM ago_constitution_emergencies WHERE tenant_id=%s AND id=%s", (tenant,str(UUID(data["emergency_id"]))),
                ).fetchone()
                if not incident:
                    raise LookupError("Emergency not found")
                postmortem = bounded(data["postmortem"])
                recovery = bounded(data["recovery_evidence"])
                signature = digest({"emergency_digest":incident["digest"],"postmortem":postmortem,"recovery_evidence":recovery})
                identifier = str(uuid4())
                approval = self.propose(tenant_id=tenant,requester_id=actor.subject,
                           action=f"constitution:emergency-review:{identifier}:{signature}")
                self.connection.execute(
                    """INSERT INTO ago_constitution_emergency_reviews
                       (id,tenant_id,emergency_id,actor_id,postmortem,recovery_evidence,digest,approval_id)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
                    (identifier,tenant,incident["id"],actor.subject,postmortem,recovery,signature,approval.request_id),
                )
                return {"id":identifier,"approval_id":approval.request_id,"applied":False}
            if command == "close-incident":
                review = self.connection.execute(
                    "SELECT * FROM ago_constitution_emergency_reviews WHERE tenant_id=%s AND id=%s",(tenant,str(UUID(data["review_id"]))),
                ).fetchone()
                if not review:
                    raise LookupError("Incident review not found")
                if str(review["actor_id"])!=actor.subject:
                    raise PermissionError("Original human review requester required")
                approval = self.connection.execute(
                    "SELECT status,reviewer_id FROM ago_approval_requests WHERE tenant_id=%s AND id=%s",(tenant,review["approval_id"]),
                ).fetchone()
                if not approval or approval["status"]!="approved" or str(approval["reviewer_id"])==actor.subject:
                    raise PermissionError("Independent reviewed recovery required")
                prior = self.connection.execute(
                    "SELECT review_id FROM ago_constitution_emergency_closures WHERE tenant_id=%s AND emergency_id=%s", (tenant,review["emergency_id"]),
                ).fetchone()
                if prior and str(prior["review_id"])!=str(review["id"]):
                    raise PermissionError("Incident already closed under different immutable review")
                if not prior:
                    self.connection.execute(
                        """INSERT INTO ago_constitution_emergency_closures(tenant_id,emergency_id,review_id,actor_id)
                           VALUES(%s,%s,%s,%s)""",(tenant,review["emergency_id"],review["id"],actor.subject),
                    )
                return {"emergency_id":str(review["emergency_id"]),"closed":True,"idempotent":bool(prior)}
            raise ValueError("Unknown constitutional command")
