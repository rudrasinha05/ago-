"""AGO local company documents: explicit person-level access, not GitHub ACLs.

Company read permissions and project assignment alone NEVER reveal document bodies.
Only an active human founder may create, revise, grant or revoke. An explicitly
granted active human with real project accountability/delegation may read one doc.
AI worker document retrieval is deliberately denied until scoped agent identities
and a separately reviewed data-minimization policy are implemented.
"""
from __future__ import annotations

from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope


class DocumentVault:
    def __init__(self, connection: DatabaseConnection,
                 *, repositories: RepositoryScope | None = None):
        self.db = connection

    def _founder(self, tenant: str, actor: str) -> bool:
        return self.db.execute("""
            SELECT 1 FROM ago_users u
            JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
            JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
            WHERE u.tenant_id=%s AND u.id=%s AND u.active
              AND e.kind='human' AND r.role='founder' LIMIT 1
        """,(tenant,actor)).fetchone() is not None

    def _project_owned(self, tenant: str, project: str, founder: str) -> None:
        row=self.db.execute("""
            SELECT 1 FROM ago_founder_intakes WHERE tenant_id=%s AND id=%s
              AND founder_id=%s
        """,(tenant,project,founder)).fetchone()
        if row is None:
            raise PermissionError("Founder-owned project required")

    def _document(self, tenant: str, document: str):
        return self.db.execute("""
            SELECT d.id,d.project_id,d.created_by,d.title,d.classification,d.created_at
            FROM ago_company_documents d WHERE d.tenant_id=%s AND d.id=%s
        """,(tenant,document)).fetchone()

    def _project_member(self, tenant: str, project: str, employee: str) -> bool:
        return self.db.execute("""
            SELECT 1 FROM ago_founder_intakes i
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
              AND l.intake_id=i.id
            WHERE i.tenant_id=%s AND i.id=%s
              AND (l.accountable_manager_id=%s
                 OR EXISTS(
                   SELECT 1 FROM ago_project_stage_delegation_activations a
                   WHERE a.tenant_id=i.tenant_id AND a.intake_id=i.id
                     AND a.assignee_id=%s))
        """,(tenant,project,employee,employee)).fetchone() is not None

    def _can_read(self, tenant: str, actor: str, doc) -> bool:
        if self._founder(tenant,actor) and str(doc["created_by"])==actor:
            return True
        if doc["classification"]!="project_restricted":
            return False
        valid=self.db.execute("""
            SELECT 1 FROM ago_users u JOIN ago_employees e
              ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
            WHERE u.tenant_id=%s AND u.id=%s AND u.active
        """,(tenant,actor)).fetchone()
        if not valid or not self._project_member(tenant,str(doc["project_id"]),actor):
            return False
        event=self.db.execute("""
            SELECT event FROM ago_company_document_acl_events
            WHERE tenant_id=%s AND document_id=%s AND grantee_id=%s
            ORDER BY id DESC LIMIT 1
        """,(tenant,str(doc["id"]),actor)).fetchone()
        return event is not None and event["event"]=="grant"

    def _audit(self, tenant: str, document: str, actor: str, action: str):
        self.db.execute("""
            INSERT INTO ago_company_document_access_audit
              (tenant_id,document_id,actor_id,action) VALUES (%s,%s,%s,%s)
        """,(tenant,document,actor,action))

    @staticmethod
    def _identifiers(*ids: str) -> None:
        for identifier in ids:
            UUID(identifier)

    def create(self, tenant: str, actor: str, project: str, title: str,
               body: str, classification: str) -> dict:
        self._identifiers(tenant,actor,project)
        if not 1<=len(title.strip())<=180 or not 1<=len(body)<=20000:
            raise ValueError("Document title/body length invalid")
        if classification not in ("founder_only","project_restricted"):
            raise ValueError("Unknown document classification")
        with self.db.transaction():
            if not self._founder(tenant,actor):
                raise PermissionError("Only an active human founder can create documents")
            self._project_owned(tenant,project,actor)
            doc_id=str(uuid4())
            self.db.execute("""
                INSERT INTO ago_company_documents
                 (id,tenant_id,project_id,created_by,title,classification)
                VALUES (%s,%s,%s,%s,%s,%s)
            """,(doc_id,tenant,project,actor,title.strip(),classification))
            self.db.execute("""
                INSERT INTO ago_company_document_revisions
                  (id,tenant_id,document_id,revision,author_id,body)
                VALUES (%s,%s,%s,1,%s,%s)
            """,(str(uuid4()),tenant,doc_id,actor,body))
            self._audit(tenant,doc_id,actor,"revise")
        return {"id":doc_id,"project_id":project,"title":title.strip(),
                "classification":classification,"revision":1,
                "founder_only":classification=="founder_only"}

    def list(self, tenant: str, actor: str, project: str) -> list[dict]:
        self._identifiers(tenant,actor,project)
        rows=self.db.execute("""
            SELECT d.id,d.project_id,d.title,d.classification,d.created_at
            FROM ago_company_documents d WHERE d.tenant_id=%s AND d.project_id=%s
            ORDER BY d.created_at DESC,d.id DESC LIMIT 200
        """,(tenant,project)).fetchall()
        visible=[]
        for row in rows:
            full=self._document(tenant,str(row["id"]))
            if self._can_read(tenant,actor,full):
                visible.append(dict(row))
                self._audit(tenant,str(row["id"]),actor,"list")
        return visible

    def eligible_members(self, tenant: str, actor: str, project: str) -> list[dict]:
        """Return eligible active human project members for an AGO access picker."""
        self._identifiers(tenant,actor,project)
        if not self._founder(tenant,actor):
            raise PermissionError("Only founder can inspect document access candidates")
        self._project_owned(tenant,project,actor)
        return [dict(row) for row in self.db.execute("""
            SELECT e.id,e.name,e.role_title
            FROM ago_employees e
            JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id
            WHERE e.tenant_id=%s AND e.kind='human' AND u.active
              AND e.id<>%s
              AND (EXISTS(
                SELECT 1 FROM ago_founder_project_lead l
                WHERE l.tenant_id=e.tenant_id AND l.intake_id=%s
                  AND l.accountable_manager_id=e.id)
              OR EXISTS(
                SELECT 1 FROM ago_project_stage_delegation_activations d
                WHERE d.tenant_id=e.tenant_id AND d.intake_id=%s
                  AND d.assignee_id=e.id))
            ORDER BY e.name,e.id
        """,(tenant,actor,project,project)).fetchall()]

    def read(self, tenant: str, actor: str, document: str) -> dict:
        self._identifiers(tenant,actor,document)
        doc=self._document(tenant,document)
        if doc is None:
            raise LookupError("Document unavailable")
        if not self._can_read(tenant,actor,doc):
            self._audit(tenant,document,actor,"denied")
            raise PermissionError("Document access denied")
        revision=self.db.execute("""
            SELECT revision,body,author_id,created_at
            FROM ago_company_document_revisions
            WHERE tenant_id=%s AND document_id=%s ORDER BY revision DESC LIMIT 1
        """,(tenant,document)).fetchone()
        self._audit(tenant,document,actor,"read")
        return {**dict(doc),**dict(revision)}

    def revise(self, tenant: str, actor: str, document: str, body: str) -> dict:
        self._identifiers(tenant,actor,document)
        if not 1<=len(body)<=20000:
            raise ValueError("Document body length invalid")
        with self.db.transaction():
            doc=self._document(tenant,document)
            if doc is None:
                raise LookupError("Document unavailable")
            if not self._founder(tenant,actor) or str(doc["created_by"])!=actor:
                raise PermissionError("Only document founder may revise")
            # Lock immutable metadata row, never update it; serialize revision numbers.
            self.db.execute("""
                SELECT id FROM ago_company_documents
                WHERE tenant_id=%s AND id=%s FOR UPDATE
            """,(tenant,document)).fetchone()
            number=self.db.execute("""
                SELECT COALESCE(MAX(revision),0)+1 AS n
                FROM ago_company_document_revisions
                WHERE tenant_id=%s AND document_id=%s
            """,(tenant,document)).fetchone()["n"]
            self.db.execute("""
                INSERT INTO ago_company_document_revisions
                  (id,tenant_id,document_id,revision,author_id,body)
                VALUES (%s,%s,%s,%s,%s,%s)
            """,(str(uuid4()),tenant,document,number,actor,body))
            self._audit(tenant,document,actor,"revise")
        return {"id":document,"revision":number}

    def change_access(self, tenant: str, actor: str, document: str,
                      grantee: str, event: str, rationale: str) -> dict:
        self._identifiers(tenant,actor,document,grantee)
        if event not in ("grant","revoke"):
            raise ValueError("Invalid access event")
        if len(rationale.strip())<8 or len(rationale.strip())>500:
            raise ValueError("A real access rationale is required")
        with self.db.transaction():
            doc=self._document(tenant,document)
            if doc is None:
                raise LookupError("Document unavailable")
            if not self._founder(tenant,actor) or str(doc["created_by"])!=actor:
                raise PermissionError("Only founder can grant or revoke documents")
            if doc["classification"]=="founder_only":
                raise PermissionError("Founder-only documents cannot be shared")
            if grantee==actor:
                raise PermissionError("Founder needs no access grant")
            # Human identity + business necessity; AI employees do not receive
            # bearer access merely because they are present on the org chart.
            active=self.db.execute("""
                SELECT 1 FROM ago_users u JOIN ago_employees e
                  ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
                WHERE u.tenant_id=%s AND u.id=%s AND u.active
            """,(tenant,grantee)).fetchone()
            if not active:
                raise PermissionError("Active human employee identity required")
            if event=="grant" and not self._project_member(
                    tenant,str(doc["project_id"]),grantee):
                raise PermissionError("Approved project staff or manager required")
            self.db.execute("""
                INSERT INTO ago_company_document_acl_events
                  (tenant_id,document_id,grantee_id,event,actor_id,rationale)
                VALUES (%s,%s,%s,%s,%s,%s)
            """,(tenant,document,grantee,event,actor,rationale.strip()))
            self._audit(tenant,document,actor,event)
        return {"document_id":document,"grantee_id":grantee,
                "action":event,"effective":event=="grant"}

    def audit(self, tenant: str, actor: str, document: str) -> list[dict]:
        self._identifiers(tenant,actor,document)
        doc=self._document(tenant,document)
        if doc is None:
            raise LookupError("Document unavailable")
        if not self._founder(tenant,actor) or str(doc["created_by"])!=actor:
            raise PermissionError("Founder-only audit history")
        return [dict(r) for r in self.db.execute("""
            SELECT actor_id,action,occurred_at FROM ago_company_document_access_audit
            WHERE tenant_id=%s AND document_id=%s
            ORDER BY id DESC LIMIT 200
        """,(tenant,document)).fetchall()]
