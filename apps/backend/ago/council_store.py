"""M6 executive council: immutable ballots, quorum and M2 independent consent.

A passing motion remains an advisory record. It cannot execute external actions.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.governance import ApprovalRepository
from ago.security import Principal
from ago.security_controls import SecurityControls


class CouncilStore:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def _human(self, actor: Principal) -> bool:
        return (
            self.db.execute(
                """SELECT 1 FROM ago_users u
               JOIN ago_employees e ON e.id=u.id AND e.tenant_id=u.tenant_id
               WHERE u.tenant_id=%s AND u.id=%s AND u.active=true
                 AND e.kind='human'""",
                (actor.tenant_id, actor.subject),
            ).fetchone()
            is not None
        )

    def propose(
        self,
        *,
        actor: Principal,
        title: str,
        rationale: str,
        required_votes: int = 2,
    ) -> dict:
        UUID(actor.tenant_id)
        UUID(actor.subject)
        if not 1 <= len(title.strip()) <= 250:
            raise ValueError("Motion title required")
        if not 1 <= len(rationale.strip()) <= 6000:
            raise ValueError("Motion rationale required")
        if not 2 <= required_votes <= 10:
            raise ValueError("Council quorum must be 2–10")
        with self.db.transaction():
            if not self._human(actor):
                raise PermissionError("An active human must propose a council motion")
            eligible = self.db.execute(
                """SELECT count(DISTINCT u.id) AS total
                   FROM ago_users u JOIN ago_employees e
                     ON e.id=u.id AND e.tenant_id=u.tenant_id
                   JOIN ago_user_roles roles
                     ON roles.tenant_id=u.tenant_id AND roles.user_id=u.id
                   JOIN ago_role_permissions grant_row
                     ON grant_row.tenant_id=roles.tenant_id
                    AND grant_row.role=roles.role
                   WHERE u.tenant_id=%s AND u.active=true
                     AND u.id<>%s AND e.kind='human'
                     AND grant_row.permission='council:vote'""",
                (actor.tenant_id, actor.subject),
            ).fetchone()["total"]
            if eligible < required_votes:
                raise PermissionError("Insufficient independent human council voters")
            motion_id = str(uuid4())
            approval = self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id,
                action=f"council:pass:{motion_id}",
                requester_id=actor.subject,
            )
            self.db.execute(
                """INSERT INTO ago_council_motions
                   (id,tenant_id,proposer_id,title,rationale,required_votes,approval_id)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                (
                    motion_id,
                    actor.tenant_id,
                    actor.subject,
                    title.strip(),
                    rationale.strip(),
                    required_votes,
                    approval.request_id,
                ),
            )
        return {"id": motion_id, "approval_id": approval.request_id, "status": "open"}

    def vote(
        self,
        *,
        actor: Principal,
        motion_id: str,
        vote: str,
        reason: str,
    ) -> dict:
        UUID(motion_id)
        if vote not in ("yes", "no") or not 1 <= len(reason.strip()) <= 3000:
            raise ValueError("Valid council decision and explanation required")
        with self.db.transaction():
            if not self.repositories.resolve(SecurityControls).permitted(
                actor,
                "council:vote",
                actor.tenant_id,
            ) or not self._human(actor):
                raise PermissionError("Only authorized active humans may vote")
            motion = self.db.execute(
                """SELECT proposer_id,status FROM ago_council_motions
                   WHERE tenant_id=%s AND id=%s FOR UPDATE""",
                (actor.tenant_id, motion_id),
            ).fetchone()
            if motion is None:
                raise LookupError("Council motion not found")
            if motion["status"] != "open" or str(motion["proposer_id"]) == actor.subject:
                raise PermissionError("Motion closed or proposer cannot vote")
            vote_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_council_votes
                   (id,tenant_id,motion_id,voter_id,vote,reason)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (vote_id, actor.tenant_id, motion_id, actor.subject, vote, reason.strip()),
            )
        return {"id": vote_id, "motion_id": motion_id, "vote": vote}

    def finalize(self, *, actor: Principal, motion_id: str) -> str:
        UUID(motion_id)
        with self.db.transaction():
            if not self.repositories.resolve(SecurityControls).permitted(
                actor,
                "council:finalize",
                actor.tenant_id,
            ) or not self._human(actor):
                raise PermissionError("Council finalizer must be an authorized human")
            motion = self.db.execute(
                """SELECT status,required_votes,approval_id
                   FROM ago_council_motions WHERE tenant_id=%s AND id=%s
                   FOR UPDATE""",
                (actor.tenant_id, motion_id),
            ).fetchone()
            if motion is None:
                raise LookupError("Motion not found")
            if motion["status"] != "open":
                raise PermissionError("Motion already finalized")
            votes = self.db.execute(
                """SELECT vote,count(*) AS total FROM ago_council_votes
                   WHERE tenant_id=%s AND motion_id=%s GROUP BY vote""",
                (actor.tenant_id, motion_id),
            ).fetchall()
            counts = {row["vote"]: int(row["total"]) for row in votes}
            if counts.get("no", 0):
                status = "rejected"
            elif counts.get("yes", 0) >= motion["required_votes"]:
                self.repositories.resolve(ApprovalRepository).assert_executable(
                    request_id=str(motion["approval_id"]),
                    tenant_id=actor.tenant_id,
                    action=f"council:pass:{motion_id}",
                )
                status = "passed"
            else:
                raise PermissionError("Human quorum not reached")
            self.db.execute(
                """UPDATE ago_council_motions SET status=%s,finalized_at=now()
                   WHERE tenant_id=%s AND id=%s""",
                (status, actor.tenant_id, motion_id),
            )
        return status

    def list(self, *, tenant_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT m.id,m.proposer_id,m.title,m.rationale,m.required_votes,
                      m.status,m.approval_id,m.created_at,
                      count(v.id) FILTER (WHERE v.vote='yes') AS yes_votes,
                      count(v.id) FILTER (WHERE v.vote='no') AS no_votes
               FROM ago_council_motions m
               LEFT JOIN ago_council_votes v
                 ON v.tenant_id=m.tenant_id AND v.motion_id=m.id
               WHERE m.tenant_id=%s
               GROUP BY m.tenant_id,m.id
               ORDER BY m.created_at DESC,m.id LIMIT 200""",
                (tenant_id,),
            ).fetchall()
        ]

    def ballots(self, *, tenant_id: str, motion_id: str) -> list[dict]:
        return [
            dict(row)
            for row in self.db.execute(
                """SELECT voter_id,vote,reason,created_at FROM ago_council_votes
               WHERE tenant_id=%s AND motion_id=%s
               ORDER BY created_at,id LIMIT 200""",
                (tenant_id, motion_id),
            ).fetchall()
        ]
