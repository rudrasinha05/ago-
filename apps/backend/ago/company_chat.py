"""Tenant-visible company conversations. Channels are filters, never private DMs."""
from __future__ import annotations

from ago.governance import founder_solo_eligible
from uuid import UUID
from dataclasses import asdict
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.organization_store import OrganizationStore
from ago.governance import ApprovalRepository


class CompanyChat:
    def __init__(self, connection: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = connection
        self.repositories = repositories or RepositoryScope(connection)

    def channel(self, tenant, channel):
        if channel == 'global':
            return
        kind, _, identifier = channel.partition(':')
        tables = {'department': 'ago_departments', 'employee': 'ago_employees'}
        if kind not in tables:
            raise ValueError('Unknown channel')
        UUID(identifier)
        if not self.db.execute(
            f'SELECT id FROM {tables[kind]} WHERE tenant_id=%s AND id=%s',
            (tenant, identifier),
        ).fetchone():
            raise ValueError('Channel unavailable')

    def _channel_permission(self, tenant: str, actor_id: str, channel: str) -> bool:
        """Fail-closed per-channel read/write; broad company RBAC is insufficient."""
        UUID(tenant)
        UUID(actor_id)
        self.channel(tenant, channel)
        identity = self.db.execute("""
            SELECT e.id,e.department_id,e.manager_id,e.kind
            FROM ago_users u JOIN ago_employees e
              ON e.tenant_id=u.tenant_id AND e.id=u.id
            WHERE u.tenant_id=%s AND u.id=%s AND u.active
        """,(tenant,actor_id)).fetchone()
        if identity is None or identity['kind'] != 'human':
            return False
        if channel == 'global':
            return True
        founder = self.db.execute("""
            SELECT 1 FROM ago_user_roles r
            WHERE r.tenant_id=%s AND r.user_id=%s AND r.role='founder'
        """,(tenant,actor_id)).fetchone()
        if founder:
            return True
        kind, _, target = channel.partition(':')
        if kind == 'department':
            return str(identity['department_id']) == target
        if kind == 'employee':
            if actor_id == target:
                return True
            target_manager = self.db.execute("""
                SELECT manager_id FROM ago_employees WHERE tenant_id=%s AND id=%s
            """,(tenant,target)).fetchone()
            return (target_manager is not None and
                    target_manager['manager_id'] is not None and
                    str(target_manager['manager_id']) == actor_id)
        return False

    def list(self, tenant, channel, before, limit, reader_id: str | None = None):
        self.channel(tenant, channel)
        if reader_id is None:
            raise PermissionError('Authenticated company reader required')
        UUID(reader_id)
        if not self._channel_permission(tenant,reader_id,channel):
            raise PermissionError('Channel access denied')
        founder=self.db.execute("""
            SELECT 1 FROM ago_user_roles WHERE tenant_id=%s AND user_id=%s
              AND role='founder'
        """,(tenant,reader_id)).fetchone() is not None
        # Founder may view the entire global audit timeline; normal employees
        # receive actual global-channel messages only. No synthetic channel IDs.
        # A department includes its employee conversations and task events.
        rows = self.db.execute('''SELECT c.*, parent.body AS reply_body, parent.author_name AS reply_author FROM ago_company_chat c LEFT JOIN ago_company_chat parent ON parent.tenant_id=c.tenant_id AND parent.id=c.reply_to AND parent.channel=c.channel
          WHERE c.tenant_id=%s AND (%s='global' OR c.channel=%s OR
            (%s LIKE 'department:%%' AND c.employee_id IN
              (SELECT id FROM ago_employees WHERE tenant_id=%s AND department_id::text=substring(%s from 12))))
          AND (%s::bigint IS NULL OR c.id < %s)
          AND (%s::boolean OR c.channel='global' OR %s<>'global')
          AND (c.kind<>'project' OR EXISTS (
              SELECT 1 FROM ago_founder_intakes i
              WHERE i.tenant_id=c.tenant_id AND i.founder_id=%s))
          AND (parent.kind IS DISTINCT FROM 'project' OR EXISTS (
              SELECT 1 FROM ago_founder_intakes i
              WHERE i.tenant_id=parent.tenant_id AND i.founder_id=%s))
          ORDER BY c.id DESC LIMIT %s''',
          (tenant, channel, channel, channel, tenant, channel, before, before,
           founder,channel,reader_id,reader_id,limit+1)).fetchall()
        return {'items': list(reversed(rows[:limit])),
                'next_before': rows[limit-1]['id'] if len(rows)>limit else None}

    def send(self, actor, channel, body, reply_to, operation_key):
        self.channel(actor.tenant_id, channel)
        if not self._channel_permission(actor.tenant_id,actor.subject,channel):
            raise PermissionError('Channel access denied')
        body = body.strip()
        if not body:
            raise ValueError('Write a message first')
        with self.db.transaction():
            if reply_to is not None:
                parent = self.db.execute("""
                    SELECT channel,kind FROM ago_company_chat
                    WHERE tenant_id=%s AND id=%s
                """,(actor.tenant_id,reply_to)).fetchone()
                if parent is None or parent['channel']!=channel or parent['kind']=='project':
                    raise ValueError('Reply unavailable')
            author = self.db.execute("SELECT COALESCE(e.name, 'AGO member') AS display_name FROM ago_users u LEFT JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id WHERE u.tenant_id=%s AND u.id=%s",
                                     (actor.tenant_id, actor.subject)).fetchone()
            row = self.db.execute('''INSERT INTO ago_company_chat
              (tenant_id,channel,author_id,author_name,body,reply_to,operation_key,employee_id)
              VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
              ON CONFLICT (tenant_id,author_id,operation_key) DO NOTHING RETURNING *''',
              (actor.tenant_id, channel, actor.subject, author['display_name'], body,
               reply_to, operation_key, channel[9:] if channel.startswith('employee:') else None)).fetchone()
            if row is None:
                row = self.db.execute('''SELECT * FROM ago_company_chat
                  WHERE tenant_id=%s AND author_id=%s AND operation_key=%s''',
                  (actor.tenant_id, actor.subject, operation_key)).fetchone()
                if (row['channel'], row['body'], row['reply_to']) != (channel, body, reply_to):
                    raise ValueError('Retry key already used for a different message')
            elif channel.startswith('employee:') and self._asks_work_status(body):
                # A reply from verified task rows is useful without an LLM.
                # Label it as automated status, never pretend an AI replied.
                self._record_status_reply(actor.tenant_id, channel, row['id'])
            return row

    @staticmethod
    def _asks_work_status(body: str) -> bool:
        question=body.strip().lower()
        return any(term in question for term in (
            'what are you working on', 'what are you doing',
            'current work', 'current task', 'assigned task', 'task status',
            'work status', 'work update', 'status update',
            'kis kaam', 'kya kaam', 'kaun sa kaam', 'kya kar rahe',
        ))

    def _record_status_reply(self, tenant_id: str, channel: str, parent_id: int) -> None:
        """A DB-grounded status reply. Not a language-model employee response."""
        employee_id=channel.removeprefix('employee:')
        worker=self.db.execute("""
            SELECT name FROM ago_employees WHERE tenant_id=%s AND id=%s
        """,(tenant_id,employee_id)).fetchone()
        if worker is None:
            return
        tasks=self.db.execute("""
            SELECT action,status,updated_at
            FROM ago_governed_tasks
            WHERE tenant_id=%s AND assignee_id=%s
            ORDER BY updated_at DESC,id DESC LIMIT 6
        """,(tenant_id,employee_id)).fetchall()
        if tasks:
            lines=['Recorded assigned work for '+worker['name']+':']
            lines.extend('- '+t['action'][:180]+' — '+t['status'] for t in tasks)
            lines.append('This is an automatic AGO database status reply, not an AI-generated response.')
            response='\n'.join(lines)
        else:
            response=(worker['name']+' has no assigned governed tasks currently recorded in AGO. '
                      'Other external activity cannot be verified. '
                      'This is an automatic database status reply, not an AI-generated response.')
        self.db.execute("""
            INSERT INTO ago_company_chat
              (tenant_id,channel,author_id,author_name,body,reply_to,kind,employee_id)
            VALUES (%s,%s,NULL,%s,%s,%s,'message',%s)
        """,(tenant_id,channel,'AGO work status · '+worker['name'],
              response,parent_id,employee_id))

    def activity(self, tenant_id, reader_id: str | None = None):
        if reader_id is None:
            raise PermissionError('Authenticated activity reader required')
        UUID(tenant_id)
        UUID(reader_id)
        return self.db.execute('''SELECT t.*, p.title AS project_name,
      p.id AS plan_id FROM ago_governed_tasks t
      LEFT JOIN ago_plan_steps s ON s.tenant_id=t.tenant_id AND s.task_id=t.id
      LEFT JOIN ago_strategy_plans p ON p.tenant_id=s.tenant_id AND p.id=s.plan_id
      LEFT JOIN ago_founder_intakes i ON i.tenant_id=p.tenant_id AND i.plan_id=p.id
      LEFT JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id AND l.intake_id=i.id
      WHERE t.tenant_id=%s
        AND (
          i.founder_id=%s OR l.accountable_manager_id=%s
          OR EXISTS (SELECT 1 FROM ago_project_stage_delegation_activations a
             WHERE a.tenant_id=i.tenant_id AND a.intake_id=i.id
               AND a.assignee_id=%s)
          OR (i.id IS NULL AND (
               t.assignee_id=%s
               OR EXISTS (SELECT 1 FROM ago_user_roles r
                 JOIN ago_users u ON u.tenant_id=r.tenant_id AND u.id=r.user_id
                 JOIN ago_employees e ON e.tenant_id=u.tenant_id AND e.id=u.id
                 WHERE r.tenant_id=t.tenant_id AND r.user_id=%s
                   AND r.role='founder' AND u.active AND e.kind='human')
             ))
        )
      ORDER BY t.updated_at DESC''', (tenant_id,reader_id,reader_id,reader_id,reader_id,reader_id)).fetchall()

    def staff(self, actor, department_id, manager_id, name, requirement, operation_key):
        db = self.db
        with db.transaction():
            # Serializes retries and same-department hiring without granting execution rights.
            department = db.execute('SELECT id FROM ago_departments WHERE tenant_id=%s AND id=%s FOR UPDATE',
                                    (actor.tenant_id, str(department_id))).fetchone()
            if not department:
                raise ValueError('Department unavailable')
            if not name.strip() or len(requirement.strip()) < 10:
                raise ValueError('A role and substantive requirement are required')
            prior = db.execute('SELECT * FROM ago_company_chat WHERE tenant_id=%s AND author_id=%s AND operation_key=%s',
                               (actor.tenant_id, actor.subject, str(operation_key))).fetchone()
            body = f'New AI role: {name.strip()}\nRequirement: {requirement.strip()}\nManager: {manager_id or "Department root"}'
            channel = 'department:' + str(department_id)
            if prior:
                if prior['kind'] != 'staffing' or prior['body'] != body or prior['channel'] != channel:
                    raise ValueError('Retry key already used')
                return {'id': prior['employee_id'], 'reused': True}
            duplicate = db.execute('SELECT id FROM ago_employees WHERE tenant_id=%s AND department_id=%s AND lower(name)=lower(%s)',
                                   (actor.tenant_id, str(department_id), name.strip())).fetchone()
            if duplicate:
                raise ValueError('This role already exists in the department; select it on the map')
            employee = self.repositories.resolve(OrganizationStore).hire(
                tenant_id=actor.tenant_id, department_id=str(department_id), name=name,
                kind='ai', manager_id=str(manager_id) if manager_id else None)
            db.execute("""
                UPDATE ago_employees SET role_title=%s,core_responsibilities=%s
                WHERE tenant_id=%s AND id=%s
            """,(name.strip(),requirement.strip(),actor.tenant_id,employee.id))
            row = self.send(actor, channel, body, None, str(operation_key))
            db.execute("UPDATE ago_company_chat SET kind='staffing',employee_id=%s WHERE tenant_id=%s AND id=%s",
                       (employee.id, actor.tenant_id, row['id']))
            return asdict(employee)

    def notifications(self, tenant_id: str, reader_id: str | None = None,
                      after_id: int | None = None) -> dict:
        """Cursor through every actual event without leaking unrelated employees.

        On first load (no cursor) return newest 100 descending as before.
        Once the browser has a watermark, advance 100 events at a time in
        ascending ID order. Each unconsumed page remains available next poll.
        """
        UUID(tenant_id)
        if reader_id is None:
            raise PermissionError('Authenticated notification reader required')
        UUID(reader_id)
        if after_id is not None and (type(after_id) is not int or after_id < 0):
            raise ValueError('Positive notification cursor required')
        founder=self.db.execute("""
            SELECT 1 FROM ago_users u JOIN ago_employees e
              ON e.tenant_id=u.tenant_id AND e.id=u.id AND e.kind='human'
            JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
              AND r.role='founder'
            WHERE u.tenant_id=%s AND u.id=%s AND u.active
        """,(tenant_id,reader_id)).fetchone() is not None
        kinds="('status','report','staffing','github','qa','docs','project')" if founder else (
            "('status','report','staffing','github','qa','docs')")
        visibility="" if founder else " AND employee_id=%s"
        params=[tenant_id]
        if not founder:
            params.append(reader_id)
        cursor_filter=""
        if after_id is not None:
            cursor_filter=" AND id>%s"
            params.append(after_id)
        order="ASC" if after_id is not None else "DESC"
        records=self.db.execute(f"""
            SELECT id,employee_id,task_id,body,kind,created_at
            FROM ago_company_chat
            WHERE tenant_id=%s {visibility} AND kind IN {kinds}
            {cursor_filter} ORDER BY id {order} LIMIT %s
        """,tuple([*params,101 if after_id is not None else 100])).fetchall()
        recent=list(records[:100])
        if founder:
            rows=self.db.execute("""
                SELECT e.id AS employee_id, COUNT(c.id) AS event_count
                FROM ago_employees e
                LEFT JOIN ago_company_chat c ON c.tenant_id=e.tenant_id
                  AND c.employee_id=e.id AND c.kind IN
                  ('status','report','staffing','github','qa','docs','project')
                WHERE e.tenant_id=%s
                GROUP BY e.id ORDER BY e.id
            """,(tenant_id,)).fetchall()
            counts={str(row["employee_id"]):int(row["event_count"]) for row in rows}
        else:
            count=self.db.execute("""
                SELECT COUNT(*) AS n FROM ago_company_chat
                WHERE tenant_id=%s AND employee_id=%s
                  AND kind IN ('status','report','staffing','github','qa','docs')
            """,(tenant_id,reader_id)).fetchone()
            counts={reader_id:int(count["n"])}
        return {
            "by_employee":counts,
            "recent":[dict(row) for row in recent],
            "has_more":len(records)>100,
            "event_type":"committed_work_event",
        }


    def staffing_proposals(self, actor, project_id: str) -> dict:
        """Read-only CEO-accountable gap suggestions, never automatic hiring."""
        import hashlib

        UUID(actor.tenant_id)
        UUID(actor.subject)
        UUID(project_id)
        if 'founder' not in actor.roles:
            raise PermissionError('Only founder may inspect internal staffing needs')
        project=self.db.execute("""
            SELECT i.id,i.title,p.status
            FROM ago_founder_intakes i
            JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            JOIN ago_users u ON u.tenant_id=i.tenant_id AND u.id=i.founder_id AND u.active
            JOIN ago_employees founder ON founder.tenant_id=u.tenant_id
                 AND founder.id=u.id AND founder.kind='human'
            WHERE i.tenant_id=%s AND i.id=%s AND i.founder_id=%s
        """,(actor.tenant_id,project_id,actor.subject)).fetchone()
        if project is None or project["status"] != "active":
            raise PermissionError('Founder-owned active approved project required')
        chief=self.db.execute("""
            SELECT e.id FROM ago_company_board_appointments b
            JOIN ago_employees e ON e.tenant_id=b.tenant_id AND e.id=b.employee_id
            WHERE b.tenant_id=%s AND b.seat='Strategy & Vision' AND e.kind='ai'
        """,(actor.tenant_id,)).fetchone()
        if chief is None:
            raise PermissionError('Real founder-appointed AI CEO required')
        stages=self.db.execute("""
            SELECT stage,position,suggested_assignee_id
            FROM ago_founder_intake_stages
            WHERE tenant_id=%s AND intake_id=%s ORDER BY position
        """,(actor.tenant_id,project_id)).fetchall()
        titles=self.db.execute("""
            SELECT DISTINCT lower(trim(role_title)) AS role
            FROM ago_employees
            WHERE tenant_id=%s AND kind='ai' AND role_title IS NOT NULL
        """,(actor.tenant_id,)).fetchall()
        existing={str(row["role"]) for row in titles}
        roles={
            'discovery':'Research Analyst',
            'architecture':'Solution Architect',
            'implementation':'Software Developer',
            'quality':'Independent QA Engineer',
            'release':'Release Engineer',
        }
        proposals=[]
        for stage in stages:
            if stage["suggested_assignee_id"] is not None:
                continue
            role=roles.get(stage["stage"])
            if role is None:
                raise ValueError('Unknown founder project stage')
            proposals.append({
                "stage":stage["stage"],
                "suggested_role":role,
                "existing_specialization_recorded":role.lower() in existing,
                "decision":"review_existing_staff" if role.lower() in existing
                           else "propose_specialist_staffing",
            })
        digest=hashlib.sha256((
            project_id+"|"+str(chief["id"])+"|"+
            "|".join(p["stage"]+":"+p["suggested_role"] for p in proposals)
        ).encode()).hexdigest()
        return {
            "kind":"ago_p1_readonly_staffing_proposals",
            "project_id":project_id,
            "ceo_employee_id":str(chief["id"]),
            "proposals":proposals,
            "source_sha256":digest,
            "is_live_project_evidence":True,
            "charter_granted":False,
            "personnel_hired":False,
            "permission_granted":False,
            "requires_founder_review":True,
        }

    def ceo_reconcile(self, actor, project_id: str) -> dict:
        """Bounded CEO-operational authorization for ONE founder-approved project.

        Executed only with a signed founder session. The CEO's identity comes from
        the persisted board seat; no client-supplied AI actor or model text has
        approval authority. Decisions are audited under the CEO employee ID;
        the initiating founder is recorded in the reason.
        """
        from ago.governance import ApprovalRepository
        from uuid import UUID, uuid4
        UUID(actor.tenant_id)
        UUID(actor.subject)
        UUID(project_id)
        if 'founder' not in actor.roles or not founder_solo_eligible(
            self.db, actor.tenant_id, actor.subject
        ):
            raise PermissionError('Only the authenticated founder can initiate CEO reconciliation')
        with self.db.transaction():
            company = self.db.execute(
                "SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                (actor.tenant_id,)
            ).fetchone()
            if not company:
                raise LookupError('Company unavailable')
            board = self.db.execute("""
                SELECT e.id,e.name,e.kind,e.role_title
                FROM ago_company_board_appointments b
                JOIN ago_employees e ON e.tenant_id=b.tenant_id
                  AND e.id=b.employee_id
                WHERE b.tenant_id=%s AND b.seat='Strategy & Vision'
            """, (actor.tenant_id,)).fetchone()
            if not board or board['kind']!='ai':
                raise PermissionError('An actual appointed AI CEO is required')
            project = self.db.execute("""
                SELECT i.id,i.founder_id,p.id AS plan_id,p.status,p.approval_id,
                       a.status AS founder_approval,a.reviewer_id AS founder_decider
                FROM ago_founder_intakes i
                JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
                LEFT JOIN ago_approval_requests a
                   ON a.tenant_id=p.tenant_id AND a.id=p.approval_id
                WHERE i.tenant_id=%s AND i.id=%s FOR UPDATE OF i
            """, (actor.tenant_id,project_id)).fetchone()
            if not project:
                raise LookupError('Founder project unavailable')
            if (str(project['founder_id'])!=actor.subject or project['status']!='active'
                    or project['founder_approval']!='approved'
                    or str(project['founder_decider'])!=actor.subject):
                raise PermissionError('Exact Founder-approved ACTIVE project required')
            rows = self.db.execute("""
                SELECT t.id,t.action,t.assignee_id,t.status,t.approval_id,ps.position
                FROM ago_plan_steps ps
                JOIN ago_governed_tasks t ON t.tenant_id=ps.tenant_id
                  AND t.id=ps.task_id
                WHERE ps.tenant_id=%s AND ps.plan_id=%s
                ORDER BY ps.position,t.id FOR UPDATE OF t
            """, (actor.tenant_id,str(project['plan_id']))).fetchall()
            checked=0
            authorized=[]
            blocked=[]
            for task in rows:
                action=task['action']
                if task['status'] not in ('proposed','waiting_approval'):
                    continue
                if action not in ('internal:brief','research:brief','project:plan'):
                    blocked.append(str(task['id']))
                    continue
                if str(task['assignee_id'])==str(board['id']):
                    blocked.append(str(task['id']))
                    continue
                # Task submission remains owned by ConsoleService/TaskStore.
                # The initiating workflow first requests exact task approval.
                if task['status']=='proposed':
                    blocked.append(str(task['id']))
                    continue
                approval_id=str(task['approval_id']) if task['approval_id'] else None
                if not approval_id:
                    blocked.append(str(task['id']))
                    continue
                receipt=self.db.execute("""
                    SELECT id,status,action,requester_id FROM ago_approval_requests
                    WHERE tenant_id=%s AND id=%s FOR UPDATE
                """,(actor.tenant_id,approval_id)).fetchone()
                if not receipt or receipt['action']!=action:
                    blocked.append(str(task['id']))
                    continue
                if receipt['status']!='pending':
                    continue
                # Approval storage belongs to Governance, which rechecks every
                # record and board identity inside this same transaction.
                reason=('CEO scope verified: approved project '+project_id+
                        '; task '+str(task['id'])+'; Founder session '+actor.subject)
                self.repositories.resolve(ApprovalRepository).approve_ceo_project_task(
                    tenant_id=actor.tenant_id, founder_id=actor.subject,
                    ceo_id=str(board['id']), project_id=project_id,
                    task_id=str(task['id']), approval_id=approval_id, action=action,
                    reason=reason,
                )
                checked+=1
                authorized.append(str(task['id']))
            # Founder approves a FULL proposal once. The appointed CEO may
            # adopt only the pre-recorded exact stage staffing suggestions.
            # Extraordinary changes still require a new Founder scope decision.
            approved_stages=[]
            blocked_stages=[]
            stage_rows=self.db.execute("""
                SELECT s.stage,s.suggested_assignee_id,s.plan_step_id,
                       step.assignee_id AS planned_worker
                FROM ago_founder_intake_stages s
                LEFT JOIN ago_plan_steps step
                  ON step.tenant_id=s.tenant_id AND step.id=s.plan_step_id
                WHERE s.tenant_id=%s AND s.intake_id=%s
                ORDER BY CASE s.stage WHEN 'discovery' THEN 1
                   WHEN 'architecture' THEN 2 WHEN 'implementation' THEN 3
                   WHEN 'quality' THEN 4 ELSE 5 END
            """,(actor.tenant_id,project_id)).fetchall()
            implementation=next((s['suggested_assignee_id'] for s in stage_rows
                                if s['stage']=='implementation'),None)
            manager=self.db.execute("""
                SELECT accountable_manager_id FROM ago_founder_project_lead
                WHERE tenant_id=%s AND intake_id=%s
            """,(actor.tenant_id,project_id)).fetchone()
            manager_id=str(manager['accountable_manager_id']) if manager else None
            for stage in stage_rows:
                stage_name=stage['stage']
                worker_id=(str(stage['suggested_assignee_id'])
                           if stage['suggested_assignee_id'] else None)
                if not worker_id or worker_id==str(board['id']):
                    blocked_stages.append(stage_name)
                    continue
                if (stage['planned_worker'] is not None and
                        str(stage['planned_worker'])!=worker_id):
                    blocked_stages.append(stage_name)
                    continue
                if stage_name=='quality' and (
                        worker_id==manager_id or
                        (implementation is not None and
                         worker_id==str(implementation))):
                    blocked_stages.append(stage_name)
                    continue
                eligible=self.db.execute("""
                    SELECT 1 FROM ago_employees
                    WHERE tenant_id=%s AND id=%s AND kind='ai'
                """,(actor.tenant_id,worker_id)).fetchone()
                if not eligible:
                    blocked_stages.append(stage_name)
                    continue
                activation=self.db.execute("""
                    SELECT id FROM ago_project_stage_delegation_activations
                    WHERE tenant_id=%s AND intake_id=%s AND stage=%s
                """,(actor.tenant_id,project_id,stage_name)).fetchone()
                if activation:
                    continue
                prior=self.db.execute("""
                    SELECT id FROM ago_project_stage_delegation_proposals
                    WHERE tenant_id=%s AND intake_id=%s AND stage=%s
                """,(actor.tenant_id,project_id,stage_name)).fetchone()
                if prior:
                    # Never silently override a pending manual staffing request.
                    blocked_stages.append(stage_name)
                    continue
                proposal_id=str(uuid4())
                approval=self.repositories.resolve(ApprovalRepository).propose(
                    tenant_id=actor.tenant_id, requester_id=actor.subject,
                    action='company:stage-delegation:'+proposal_id,
                )
                self.db.execute("""
                    INSERT INTO ago_project_stage_delegation_proposals
                      (id,tenant_id,intake_id,stage,assignee_id,requester_id,approval_id)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,(proposal_id,actor.tenant_id,project_id,stage_name,
                     worker_id,actor.subject,approval.request_id))
                reason=('CEO verified original Founder-approved staffing scope for '+
                        project_id+' stage '+stage_name+'; authorized Founder session '+
                        actor.subject)
                self.repositories.resolve(ApprovalRepository).approve_ceo_project_stage(
                    tenant_id=actor.tenant_id, founder_id=actor.subject,
                    ceo_id=str(board['id']), project_id=project_id,
                    proposal_id=proposal_id, approval_id=approval.request_id,
                    reason=reason,
                )
                self.db.execute("""
                    INSERT INTO ago_project_stage_delegation_activations
                      (id,tenant_id,proposal_id,intake_id,stage,assignee_id,applied_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s)
                """,(str(uuid4()),actor.tenant_id,proposal_id,project_id,
                     stage_name,worker_id,actor.subject))
                self.db.execute("""
                    INSERT INTO ago_company_chat
                      (tenant_id,channel,author_id,author_name,body,kind,employee_id)
                    VALUES (%s,'global',%s,'Company CEO',%s,'project',%s)
                """,(actor.tenant_id,actor.subject,
                     'Verified approved project stage '+stage_name+' assigned to '+
                     worker_id+'; no model or external action launched.',worker_id))
                approved_stages.append(stage_name)
            return {
                'project_id':project_id,
                'ceo_id':str(board['id']),
                'ceo_name':board['name'],
                'verified_task_count':checked,
                'approved_stage_names':approved_stages,
                'approved_stage_count':len(approved_stages),
                'blocked_stage_names':blocked_stages,
                'approved_task_ids':authorized,
                'blocked_task_ids':blocked,
                'tasks_executed':0,
                'external_tools_authorized':False,
                'evidence':'stored project scope, actual board CEO, immutable approval records',
                'verification_kind':'deterministic_project_scope_gate',
            }

    def governance(self, tenant_id: str) -> dict:
        """Read explicit appointments and employee accountability, not inferred job titles."""
        employees = self.db.execute("""
            SELECT e.id,e.name,e.kind,e.department_id,e.manager_id,
                   e.role_title,e.core_responsibilities,e.extra_responsibilities
            FROM ago_employees e WHERE e.tenant_id=%s ORDER BY e.name
        """, (tenant_id,)).fetchall()
        seats = self.db.execute("""
            SELECT b.seat,b.employee_id,b.appointed_by,b.appointed_at
            FROM ago_company_board_appointments b WHERE b.tenant_id=%s
            ORDER BY b.seat
        """, (tenant_id,)).fetchall()
        return {"employees": [dict(e) for e in employees],
                "board": [dict(s) for s in seats],
                "board_grants_authority": False}

    def set_reporting_manager(self, actor, employee_id: str,
                              manager_id: str | None) -> dict:
        """Founder-only recorded hierarchy; no cycles or cross-tenant managers."""
        UUID(employee_id)
        if manager_id:
            UUID(manager_id)
        if 'founder' not in actor.roles:
            raise PermissionError('Only the founder can change reporting lines')
        if manager_id==employee_id:
            raise ValueError('Employee cannot manage themselves')
        with self.db.transaction():
            self.db.execute(
                'SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE',
                (actor.tenant_id,)
            ).fetchone()
            worker=self.db.execute(
                'SELECT id,manager_id FROM ago_employees WHERE tenant_id=%s AND id=%s',
                (actor.tenant_id,employee_id)
            ).fetchone()
            if worker is None:
                raise LookupError('Employee not in this company')
            if manager_id:
                manager=self.db.execute(
                    'SELECT id FROM ago_employees WHERE tenant_id=%s AND id=%s',
                    (actor.tenant_id,manager_id)
                ).fetchone()
                if not manager:
                    raise LookupError('Reporting manager not in this company')
                chain=self.db.execute("""
                    WITH RECURSIVE chain AS (
                        SELECT id,manager_id,ARRAY[id] AS path
                        FROM ago_employees WHERE tenant_id=%s AND id=%s
                        UNION ALL
                        SELECT boss.id,boss.manager_id,chain.path || boss.id
                        FROM chain JOIN ago_employees boss
                          ON boss.tenant_id=%s AND boss.id=chain.manager_id
                        WHERE NOT boss.id=ANY(chain.path)
                    )
                    SELECT EXISTS(SELECT 1 FROM chain WHERE id=%s) AS circular
                """,(actor.tenant_id,manager_id,actor.tenant_id,employee_id)).fetchone()
                if chain and chain['circular']:
                    raise PermissionError('Circular reporting chain rejected')
            saved=self.db.execute("""
                UPDATE ago_employees SET manager_id=%s WHERE tenant_id=%s AND id=%s
                RETURNING id,manager_id
            """,(manager_id,actor.tenant_id,employee_id)).fetchone()
            return dict(saved)

    def profile(self, actor, employee_id: str, title: str, core: str, extra: str) -> dict:
        if "founder" not in actor.roles:
            raise PermissionError("Founder approval required to edit employee accountability")
        UUID(employee_id)
        if not 1 <= len(title.strip()) <= 150 or not 1 <= len(core.strip()) <= 3000:
            raise ValueError("Role title and core responsibilities required")
        if len(extra) > 3000:
            raise ValueError("Additional responsibilities exceed size limit")
        with self.db.transaction():
            row = self.db.execute("""
                UPDATE ago_employees SET role_title=%s,core_responsibilities=%s,
                  extra_responsibilities=%s
                WHERE tenant_id=%s AND id=%s RETURNING id,role_title,
                  core_responsibilities,extra_responsibilities
            """, (title.strip(),core.strip(),extra.strip(),actor.tenant_id,employee_id)).fetchone()
            if row is None:
                raise LookupError("Employee not found")
            return dict(row)

    def appoint(self, actor, seat: str, employee_id: str) -> dict:
        if "founder" not in actor.roles:
            raise PermissionError("Only the founder can record explicit board appointments")
        allowed_seats = {"Strategy & Vision","Technology Oversight","Finance & Budget",
                         "Risk & Compliance","Quality & Release"}
        if seat not in allowed_seats:
            raise ValueError("Unknown board responsibility")
        UUID(employee_id)
        with self.db.transaction():
            # Avoid a race between distinct appointments for the same tenant.
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                            (actor.tenant_id,)).fetchone()
            member = self.db.execute(
                "SELECT id FROM ago_employees WHERE tenant_id=%s AND id=%s",
                (actor.tenant_id, employee_id)).fetchone()
            if not member:
                raise LookupError("Employee is not in this company")
            current = self.db.execute("""
                SELECT employee_id FROM ago_company_board_appointments
                WHERE tenant_id=%s AND seat=%s
            """, (actor.tenant_id,seat)).fetchone()
            if current and str(current["employee_id"]) == employee_id:
                return {"seat":seat,"employee_id":employee_id,"unchanged":True,
                        "authority_granted":False}
            self.db.execute("""
                DELETE FROM ago_company_board_appointments
                WHERE tenant_id=%s AND seat=%s
            """, (actor.tenant_id,seat))
            self.db.execute("""
                INSERT INTO ago_company_board_appointments
                (tenant_id,seat,employee_id,appointed_by)
                VALUES (%s,%s,%s,%s)
            """, (actor.tenant_id,seat,employee_id,actor.subject))
        return {"seat":seat,"employee_id":employee_id,"authority_granted":False}

    def report(self, actor, kind: str, body: str, operation_key: str,
               task_id: str | None = None) -> dict:
        UUID(operation_key)
        if task_id is not None:
            UUID(task_id)
        if kind not in {"doubt","blocker","module_complete","phase_complete"}:
            raise ValueError("Unknown report type")
        if not 1 <= len(body.strip()) <= 6000:
            raise ValueError("Report must contain substantive content")
        with self.db.transaction():
            author = self.db.execute("""
                SELECT id,name,kind,manager_id FROM ago_employees
                WHERE tenant_id=%s AND id=%s
            """, (actor.tenant_id,actor.subject)).fetchone()
            if author is None or author["kind"] != "human":
                raise PermissionError("Only an authenticated human employee can submit this report")
            prior = self.db.execute("""
                SELECT * FROM ago_company_reports
                WHERE tenant_id=%s AND author_id=%s AND operation_key=%s
            """, (actor.tenant_id,actor.subject,operation_key)).fetchone()
            if prior:
                if (prior["kind"],prior["body"],str(prior["task_id"]) if prior["task_id"] else None) != (
                    kind,body.strip(),task_id):
                    raise ValueError("Idempotency key already used for a different report")
                return dict(prior)
            recipient_id = author["manager_id"]
            if not recipient_id:
                founder = self.db.execute("""
                    SELECT e.id FROM ago_employees e
                    JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id
                    JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id
                    WHERE e.tenant_id=%s AND r.role='founder' AND e.kind='human' AND u.active
                    ORDER BY e.id LIMIT 1
                """, (actor.tenant_id,)).fetchone()
                recipient_id = founder["id"] if founder else None
            if recipient_id is None or str(recipient_id) == actor.subject:
                raise PermissionError("No immediate higher authority available")
            if task_id:
                assignment = self.db.execute("""
                    SELECT id FROM ago_governed_tasks
                    WHERE tenant_id=%s AND id=%s AND assignee_id=%s
                """, (actor.tenant_id,task_id,actor.subject)).fetchone()
                if not assignment:
                    raise PermissionError("Only assigned task owner can attach a report")
            row = self.db.execute("""
                INSERT INTO ago_company_reports
                (tenant_id,author_id,recipient_id,kind,body,task_id,operation_key)
                VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (actor.tenant_id,actor.subject,str(recipient_id),kind,
                  body.strip(),task_id,operation_key)).fetchone()
            # The shared timeline intentionally excludes the report body.
            self.db.execute("""
                INSERT INTO ago_company_chat
                (tenant_id,channel,author_id,author_name,body,kind,employee_id,task_id)
                VALUES (%s,%s,%s,%s,%s,'report',%s,%s)
            """, (actor.tenant_id,"employee:"+actor.subject,actor.subject,author["name"],
                  "Submitted "+kind.replace("_"," ")+" report to immediate superior",
                  actor.subject,task_id))
        return dict(row)

    def reports(self, actor, limit: int = 100) -> list[dict]:
        if not 1 <= limit <= 100:
            raise ValueError("Invalid report history limit")
        if "founder" in actor.roles:
            rows = self.db.execute("""
                SELECT * FROM ago_company_reports WHERE tenant_id=%s
                ORDER BY id DESC LIMIT %s
            """, (actor.tenant_id,limit)).fetchall()
        else:
            rows = self.db.execute("""
                SELECT * FROM ago_company_reports
                WHERE tenant_id=%s AND (author_id=%s OR recipient_id=%s)
                ORDER BY id DESC LIMIT %s
            """, (actor.tenant_id,actor.subject,actor.subject,limit)).fetchall()
        return [dict(row) for row in rows]

    def start_project(self, actor, brief: str, operation_key: str) -> dict:
        """Atomic founder project intake. Produces a draft, not authorized execution."""
        from uuid import uuid4
        import hashlib

        if 'founder' not in actor.roles:
            raise PermissionError('Only the human founder may start a project')
        UUID(actor.tenant_id)
        UUID(actor.subject)
        UUID(operation_key)
        text = brief.strip()
        if not 20 <= len(text) <= 12000:
            raise ValueError('Project brief must contain 20–12000 characters')
        title = (text.splitlines()[0].strip() or 'Untitled project')[:220]
        digest = hashlib.sha256(text.encode('utf-8')).hexdigest()

        with self.db.transaction():
            self.db.execute('SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE',
                            (actor.tenant_id,)).fetchone()
            existing = self.db.execute("""
                SELECT * FROM ago_founder_intakes
                WHERE tenant_id=%s AND founder_id=%s AND operation_key=%s
            """, (actor.tenant_id,actor.subject,operation_key)).fetchone()
            if existing:
                if existing['brief_digest'] != digest:
                    raise ValueError('Idempotency key already used for another project')
                intake_id = str(existing['id'])
                reused = True
            else:
                employees = self.db.execute("""
                    SELECT id,name,kind,role_title,department_id,manager_id FROM ago_employees
                    WHERE tenant_id=%s ORDER BY name,id
                """, (actor.tenant_id,)).fetchall()
                # CEO owns operations after founder approves the complete plan.
                available_ai = [e for e in employees if e['kind']=='ai']
                discovery = next((e for e in available_ai
                                  if any(term in (e['name']+' '+(e['role_title'] or '')).lower()
                                         for term in ('research','analyst','product'))),None)
                # Project delivery belongs to actual top management, not a task worker.
                # A missing executive is an explicit founder escalation, never a fake CEO.
                def executive_rank(e):
                    title = (e['role_title'] or '').strip().lower()
                    name = e['name'].strip().lower()
                    if title in {'ceo','chief executive officer'} or 'chief executive officer' in title or name == 'ceo':
                        return 0
                    if title in {'coo','chief operating officer'} or name == 'coo':
                        return 1
                    if title in {'cto','chief technology officer'} or name == 'cto':
                        return 2
                    if title in {'director','managing director','general manager','project manager'}:
                        return 3
                    if title.startswith(('head of ','head -','vp ','vice president')):
                        return 4
                    return None
                supervisors = {str(e['manager_id']) for e in employees if e['manager_id']}
                management = sorted(
                    (e for e in employees
                     if str(e['id']) != actor.subject and
                     (executive_rank(e) is not None or str(e['id']) in supervisors)),
                    key=lambda e: (
                        executive_rank(e) if executive_rank(e) is not None else 5,
                        e['manager_id'] is not None, str(e['id'])
                    ),
                )
                leader = management[0] if management else next(
                    (e for e in employees if str(e['id']) == actor.subject),None
                )
                # The five reviewed Board members provide executive oversight;
                # the seven-identity local AI workflow additionally needs an
                # independent AI PROJECT manager. Never count CEO twice.
                # This flag is explicit localhost-only engineering mode; normal
                # CEO-owned project intake retains the existing contract.
                import os
                engineering_pm_mode = (
                    os.getenv('AGO_LOCAL_FULL_BOARD_REVIEW','').lower() == 'true'
                    and os.getenv('AGO_LOCAL_ENGINEERING_CANDIDATES','').lower() == 'true'
                    and os.getenv('AGO_ENVIRONMENT','development').lower()
                       in ('development','test','testing')
                )
                if engineering_pm_mode:
                    ceo_seat=self.db.execute("""
                        SELECT b.employee_id
                        FROM ago_company_board_appointments b
                        JOIN ago_employees ceo ON ceo.tenant_id=b.tenant_id
                          AND ceo.id=b.employee_id AND ceo.kind='ai'
                        WHERE b.tenant_id=%s AND b.seat='Strategy & Vision'
                    """,(actor.tenant_id,)).fetchone()
                    ceo_id=(str(ceo_seat['employee_id']) if ceo_seat else None)
                    if ceo_id:
                        pm_candidates=[
                            e for e in available_ai
                            if (e['role_title'] or '').strip().lower()
                               in ('project manager','ai project manager',
                                   'ai project manager (pm)',
                                   'technical project manager')
                            and str(e['id'])!=ceo_id
                            and str(e['manager_id'] or '')==ceo_id
                        ]
                        if pm_candidates:
                            leader=sorted(pm_candidates,key=lambda e:str(e['id']))[0]
                if leader is None:
                    raise PermissionError('Founder must exist as an employee to own delivery')
                owner_source = (
                    'executive_manager' if str(leader['id']) != actor.subject
                    else 'founder_escalation'
                )
                goal_id, plan_id, intake_id = str(uuid4()), str(uuid4()), str(uuid4())
                self.db.execute("""
                    INSERT INTO ago_goals(id,tenant_id,created_by,title,description)
                    VALUES(%s,%s,%s,%s,%s)
                """, (goal_id,actor.tenant_id,actor.subject,title,text))
                self.db.execute("""
                    INSERT INTO ago_strategy_plans(id,tenant_id,goal_id,proposer_id,title)
                    VALUES(%s,%s,%s,%s,%s)
                """, (plan_id,actor.tenant_id,goal_id,actor.subject,title))
                self.db.execute("""
                    INSERT INTO ago_founder_intakes
                    (id,tenant_id,founder_id,operation_key,brief_digest,brief,title,goal_id,plan_id)
                    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (intake_id,actor.tenant_id,actor.subject,operation_key,
                      digest,text,title,goal_id,plan_id))
                self.db.execute("""
                    INSERT INTO ago_founder_project_lead
                      (tenant_id,intake_id,accountable_manager_id,assigned_by,assignment_source)
                    VALUES (%s,%s,%s,%s,%s)
                """,(actor.tenant_id,intake_id,leader['id'],actor.subject,owner_source))
                # Only an allowlisted, bounded internal brief is seeded as an actual
                # M3 step. All later engineering stages stay explicit proposals.
                first_step = str(uuid4()) if discovery else None
                if discovery:
                    self.db.execute("""
                        INSERT INTO ago_plan_steps
                        (id,tenant_id,plan_id,position,action,assignee_id)
                        VALUES (%s,%s,%s,1,'internal:brief',%s)
                    """, (first_step,actor.tenant_id,plan_id,discovery['id']))
                stages = (
                    ('discovery','Clarify requirements, risks and measurable acceptance criteria',
                     ('research','analyst','product'), 'ai'),
                    ('architecture','Design the approved technical architecture and dependencies',
                     ('architect','technical lead','cto'), 'ai'),
                    ('implementation','Implement approved code, tests and technical documentation',
                     ('developer','engineer','programmer'), 'ai'),
                    ('quality','Record CEO-controlled QA evidence and release blockers',
                     ('quality','qa','tester'), 'ai'),
                    ('release','Prepare GitHub review package and owner release decision',
                     ('devops','release','operations','delivery'), 'ai'),
                )
                implementation_worker = None
                for index, (stage, deliverable, keywords, required_kind) in enumerate(stages,1):
                    if stage == 'discovery':
                        assignee = discovery
                    else:
                        def eligible_for_stage(e):
                            identity=(e['name']+' '+(e['role_title'] or '')).lower()
                            if not any(keyword in identity for keyword in keywords):
                                return False
                            if stage=='implementation' and any(
                                    keyword in identity for keyword in
                                    ('quality','qa specialist','qa engineer','tester')):
                                return False
                            if stage=='quality' and (
                                    str(e['id'])==str(leader['id']) or
                                    (implementation_worker is not None and
                                     str(e['id'])==str(implementation_worker['id']))):
                                return False
                            return True
                        assignee = next((e for e in available_ai
                                         if eligible_for_stage(e)),None)
                    if stage=='implementation':
                        implementation_worker=assignee
                    self.db.execute("""
                        INSERT INTO ago_founder_intake_stages
                        (tenant_id,intake_id,plan_id,position,stage,deliverable,suggested_assignee_id,plan_step_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (actor.tenant_id,intake_id,plan_id,index,stage,deliverable,
                          assignee['id'] if assignee else None,
                          first_step if stage=='discovery' else None))
                # Notify accountable management; this is a recorded assignment, not an AI run.
                self.db.execute("""
                    INSERT INTO ago_company_chat
                    (tenant_id,channel,author_id,author_name,body,kind,employee_id)
                    VALUES (%s,'global',%s,'Company Brain',
                            'Leadership accountable for delivery; founder project saved: ' || %s,
                            'project',%s)
                """, (actor.tenant_id,actor.subject,title,leader['id']))
                reused = False

            row = self.db.execute("""
                SELECT i.id,i.title,i.goal_id,i.plan_id,i.created_at,p.status AS plan_status,
              l.accountable_manager_id,e.name AS accountable_manager_name,
              e.role_title AS accountable_manager_role,
              l.assignment_source,l.commercial_objective,l.commercial_stage,
              l.verified_revenue_inr,
                    l.accountable_manager_id,l.assignment_source,
                    e.name AS accountable_manager_name,e.role_title AS accountable_manager_role,
                    l.commercial_objective,l.commercial_stage,l.verified_revenue_inr
                FROM ago_founder_intakes i JOIN ago_strategy_plans p
                  ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
                JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id AND l.intake_id=i.id
                JOIN ago_employees e ON e.tenant_id=l.tenant_id
                  AND e.id=l.accountable_manager_id
                WHERE i.tenant_id=%s AND i.id=%s
            """, (actor.tenant_id,intake_id)).fetchone()
            steps = self.db.execute("""
                SELECT s.position,s.stage,s.deliverable,s.suggested_assignee_id,
                       s.plan_step_id,e.name AS suggested_assignee_name
                FROM ago_founder_intake_stages s
                LEFT JOIN ago_employees e
                  ON e.tenant_id=s.tenant_id AND e.id=s.suggested_assignee_id
                WHERE s.tenant_id=%s AND s.intake_id=%s ORDER BY s.position
            """, (actor.tenant_id,intake_id)).fetchall()
        return {
            'id': str(row['id']), 'title':row['title'],
            'goal_id':str(row['goal_id']), 'plan_id':str(row['plan_id']),
            'created_at':row['created_at'], 'reused':reused,
            'plan_status':row['plan_status'], 'automatic_execution':False,
            'accountable_manager_id':str(row['accountable_manager_id']),
            'accountable_manager_name':row['accountable_manager_name'],
            'accountable_manager_role':row['accountable_manager_role'],
            'assignment_source':row['assignment_source'],
            'leadership_staffing_gap':row['assignment_source']=='founder_escalation',
            'commercial_objective':row['commercial_objective'],
            'commercial_stage':row['commercial_stage'],
            'verified_revenue_inr':row['verified_revenue_inr'],
            'approval_required':True,
            'stages':[{
                'position':s['position'],'stage':s['stage'],'deliverable':s['deliverable'],
                'suggested_assignee_id':str(s['suggested_assignee_id'])
                    if s['suggested_assignee_id'] else None,
                'suggested_assignee_name':s['suggested_assignee_name'],
                'plan_step_id':str(s['plan_step_id']) if s['plan_step_id'] else None,
                'staffing_required':s['suggested_assignee_id'] is None,
            } for s in steps],
        }

    def projects(self, tenant_id: str, limit: int = 30, offset: int = 0,
                 reader_id: str | None = None) -> list[dict]:
        UUID(tenant_id)
        if reader_id is None:
            raise PermissionError('Authenticated project reader required')
        UUID(reader_id)
        if not 1 <= limit <= 100 or not 0 <= offset <= 100000:
            raise ValueError('Invalid project history pagination')
        return [dict(row) for row in self.db.execute("""
            SELECT i.id,i.title,i.goal_id,i.plan_id,i.created_at,p.status AS plan_status,
              l.accountable_manager_id,e.name AS accountable_manager_name,
              e.role_title AS accountable_manager_role,l.assignment_source,
              l.commercial_objective,l.commercial_stage,l.verified_revenue_inr,
              (SELECT COUNT(*) FROM ago_founder_intake_stages s
               WHERE s.tenant_id=i.tenant_id AND s.intake_id=i.id
                 AND s.suggested_assignee_id IS NULL) AS staffing_gaps,
              (SELECT COALESCE(json_agg(json_build_object(
                  'stage',s.stage,'deliverable',s.deliverable,
                  'suggested_assignee_id',s.suggested_assignee_id,
                  'suggested_assignee_name',e.name,
                  'suggested_role',e.role_title,'plan_step_id',s.plan_step_id
               ) ORDER BY s.position),'[]'::json)
               FROM ago_founder_intake_stages s
               LEFT JOIN ago_employees e
                 ON e.tenant_id=s.tenant_id AND e.id=s.suggested_assignee_id
               WHERE s.tenant_id=i.tenant_id AND s.intake_id=i.id) AS stages
            FROM ago_founder_intakes i JOIN ago_strategy_plans p
                 ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
                 AND l.intake_id=i.id
            JOIN ago_employees e ON e.tenant_id=l.tenant_id
                 AND e.id=l.accountable_manager_id
            WHERE i.tenant_id=%s
              AND (
                i.founder_id=%s
                OR l.accountable_manager_id=%s
                OR EXISTS (
                  SELECT 1 FROM ago_project_stage_delegation_activations a
                  WHERE a.tenant_id=i.tenant_id AND a.intake_id=i.id
                    AND a.assignee_id=%s
                )
              )
            ORDER BY i.created_at DESC,i.id DESC LIMIT %s OFFSET %s
        """, (tenant_id,reader_id,reader_id,reader_id,limit,offset)).fetchall()]

    def project_details(self, tenant_id: str, project_id: str,
                        reader_id: str | None = None) -> dict:
        """Need-to-know founder, accountable manager or approved stage worker only."""
        UUID(tenant_id)
        UUID(project_id)
        if reader_id is None:
            raise PermissionError('Authenticated project reader required')
        UUID(reader_id)
        row = self.db.execute("""
            SELECT i.id,i.title,i.brief,i.created_at,i.plan_id,p.status AS plan_status,
                   l.accountable_manager_id,e.name AS accountable_manager_name,
                   l.assignment_source,l.commercial_objective,l.commercial_stage,
                   l.verified_revenue_inr
            FROM ago_founder_intakes i
            JOIN ago_strategy_plans p ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id AND l.intake_id=i.id
            JOIN ago_employees e ON e.tenant_id=l.tenant_id
              AND e.id=l.accountable_manager_id
            WHERE i.tenant_id=%s AND i.id=%s
              AND (
                i.founder_id=%s OR l.accountable_manager_id=%s
                OR EXISTS (
                  SELECT 1 FROM ago_project_stage_delegation_activations a
                  WHERE a.tenant_id=i.tenant_id AND a.intake_id=i.id
                    AND a.assignee_id=%s
                )
              )
        """,(tenant_id,project_id,reader_id,reader_id,reader_id)).fetchone()
        if row is None:
            raise LookupError('Project not found')
        stages = self.db.execute("""
            SELECT s.position,s.stage,s.deliverable,
                   s.suggested_assignee_id,e.name AS suggested_assignee_name,
                   s.plan_step_id,t.id AS task_id,t.status AS task_status,
                   t.action AS task_action,executor.name AS executing_employee,
                   q.verdict AS qa_verdict,q.evidence AS qa_evidence,
                   q.created_at AS qa_reviewed_at,ar.status AS agent_run_status,
                   ar.failure_code AS agent_failure_code,ar.started_at AS agent_started_at,
                   ar.finished_at AS agent_finished_at,
                   CASE WHEN i.founder_id=%s THEN ar.result ELSE NULL END
                       AS founder_agent_result,
                   assigned.assignee_id AS approved_assignee_id,
                   delegated.name AS approved_assignee_name,
                   assigned.applied_at AS delegated_at
            FROM ago_founder_intake_stages s
            JOIN ago_founder_intakes i ON i.tenant_id=s.tenant_id AND i.id=s.intake_id
            LEFT JOIN ago_employees e ON e.tenant_id=s.tenant_id
              AND e.id=s.suggested_assignee_id
            LEFT JOIN ago_plan_steps step ON step.tenant_id=s.tenant_id
              AND step.id=s.plan_step_id AND step.plan_id=s.plan_id
            LEFT JOIN ago_governed_tasks t ON t.tenant_id=step.tenant_id AND t.id=step.task_id
            LEFT JOIN ago_employees executor ON executor.tenant_id=t.tenant_id AND executor.id=t.assignee_id
            LEFT JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id AND q.task_id=t.id
            LEFT JOIN ago_agent_runs ar ON ar.tenant_id=t.tenant_id AND ar.task_id=t.id
            LEFT JOIN ago_project_stage_delegation_activations assigned
              ON assigned.tenant_id=s.tenant_id AND assigned.intake_id=s.intake_id
                 AND assigned.stage=s.stage
            LEFT JOIN ago_employees delegated
              ON delegated.tenant_id=assigned.tenant_id AND delegated.id=assigned.assignee_id
            WHERE s.tenant_id=%s AND s.intake_id=%s ORDER BY s.position
        """,(reader_id,tenant_id,project_id)).fetchall()
        result = dict(row)
        result['stages'] = [dict(stage) for stage in stages]
        completed = sum(s['qa_verdict']=='pass' for s in stages)
        result['qa_passed_stages'] = completed
        result['stage_count'] = len(stages)
        result['completion_percent'] = round(100*completed/max(len(stages),1))
        result['reviewed_delegations_count'] = sum(s['approved_assignee_id'] is not None for s in stages)
        result['unassigned_stages'] = sum(s['suggested_assignee_id'] is None for s in stages)
        result['running_stages'] = sum(s['task_status']=='running' for s in stages)
        result['failed_stages'] = sum(s['task_status']=='failed' or s['qa_verdict']=='fail'
                                      for s in stages)
        result['project_health'] = (
            'blocked' if result['failed_stages'] else
            'staffing_required' if result['unassigned_stages'] else
            'delivery_running' if result['running_stages'] else
            'waiting_for_qa' if any(s['task_status']=='completed' and not s['qa_verdict'] for s in stages) else
            'awaiting_governed_work'
        )
        # We do not infer a published app from the plan or a passing internal brief.
        result['status_label'] = 'under_process'
        result['verified_market_release'] = False
        result['revenue_record_status'] = (
            'no_verified_evidence' if row['verified_revenue_inr'] is None else 'recorded_amount')
        return result

    def approved_signal_project(self, actor, signal_id: str) -> dict:
        """Convert exactly one founder-approved research signal to a draft project.

        CEO remains opportunity owner, while the founder authorizes promotion;
        no code execution, automatic hiring, releases or unapproved outreach.
        """
        from uuid import uuid5
        UUID(actor.tenant_id)
        UUID(signal_id)
        if 'founder' not in actor.roles:
            raise PermissionError('Active founder required for researched project intake')
        with self.db.transaction():
            self.db.execute("SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE",
                            (actor.tenant_id,)).fetchone()
            row = self.db.execute("""
                SELECT s.id,s.title,s.source_url,s.source_name,s.source_kind,
                       s.potential_customer,s.score_basis,s.opportunity_score,s.review_status,
                       s.approval_id,s.executive_owner_id,a.status AS approval_status,
                       a.action,a.requester_id,a.reviewer_id
                FROM ago_market_signals s JOIN ago_approval_requests a
                  ON a.tenant_id=s.tenant_id AND a.id=s.approval_id
                WHERE s.tenant_id=%s AND s.id=%s FOR UPDATE OF s
            """,(actor.tenant_id,signal_id)).fetchone()
            if row is None:
                raise LookupError('Market signal not found or not nominated')
            if (row['review_status']!='shortlisted' or row['approval_status']!='approved'
                    or row['action']!='company:market-signal:'+signal_id
                    or str(row['requester_id'])!=str(row['executive_owner_id'])
                    or str(row['reviewer_id'])!=actor.subject):
                raise PermissionError('Exact founder-approved market signal required')
            # Idempotency key binds a single research observation to a single draft.
            stable_key=str(uuid5(UUID(actor.tenant_id),signal_id))
            brief=(
                'Validate opportunity: '+row['title'][:170]+'\n'
                'Research source: '+row['source_name']+' ('+row['source_kind']+')\n'
                'Source URL: '+row['source_url']+'\n'
                'Potential customer hypothesis: '+row['potential_customer']+'\n'
                'Scoring evidence: '+row['score_basis']+'\n'
                'Required first milestone: interview consented potential customers, '
                'check originality and actual demand before authorizing development.\n'
                'No claims of confirmed buyers, budget, product, publication or payment. '
                'Founder approval for this draft does not authorize external activity.'
            )[:12000]
            project=self.start_project(actor,brief,stable_key)
            self.db.execute("""
                INSERT INTO ago_market_signal_project_links
                  (tenant_id,signal_id,intake_id,linked_by,approval_id)
                VALUES (%s,%s,%s,%s,%s)
                ON CONFLICT (tenant_id,signal_id) DO NOTHING
            """,(actor.tenant_id,signal_id,project['id'],actor.subject,row['approval_id']))
            project['source_signal_id']=signal_id
            project['source_url']=row['source_url']
            project['commercial_proof']='customer_validation_pending'
            project['promotion_authorized']=False
            return project

    def propose_stage_delegation(self, actor, project_id: str, stage: str,
                                 assignee_id: str) -> dict:
        """Create a real scoped operational review, not an agent instruction."""
        from uuid import uuid4
        UUID(actor.tenant_id)
        UUID(project_id)
        UUID(assignee_id)
        if stage not in ('discovery','architecture','implementation','quality','release'):
            raise ValueError('Unknown delivery stage')
        if 'founder' not in actor.roles or not founder_solo_eligible(
            self.db, actor.tenant_id, actor.subject
        ):
            raise PermissionError('Only the authenticated active Founder may propose staffing')
        with self.db.transaction():
            project=self.db.execute("""
                SELECT i.id,i.plan_id,p.status,l.accountable_manager_id
                FROM ago_founder_intakes i JOIN ago_strategy_plans p
                  ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
                JOIN ago_founder_project_lead l
                  ON l.tenant_id=i.tenant_id AND l.intake_id=i.id
                WHERE i.tenant_id=%s AND i.id=%s FOR UPDATE OF i
            """,(actor.tenant_id,project_id)).fetchone()
            if project is None:
                raise LookupError('Project does not exist in founder company')
            if project['status'] not in ('draft','pending_approval','active'):
                raise PermissionError('Project cannot receive new delegation proposals')
            position=self.db.execute("""
                SELECT s.stage,s.plan_step_id,s.suggested_assignee_id
                FROM ago_founder_intake_stages s
                WHERE s.tenant_id=%s AND s.intake_id=%s AND s.stage=%s
            """,(actor.tenant_id,project_id,stage)).fetchone()
            if position is None:
                raise LookupError('Requested stage not found')
            worker=self.db.execute("""
                SELECT id,name,kind,role_title,manager_id
                FROM ago_employees WHERE tenant_id=%s AND id=%s
            """,(actor.tenant_id,assignee_id)).fetchone()
            if worker is None:
                raise LookupError('Selected worker not in this company')
            if worker['kind']!='ai':
                raise PermissionError('CEO delivery stages require an existing AI specialist')
            if stage=='quality' and str(worker['id'])==str(project['accountable_manager_id']):
                raise PermissionError('QA stage specialist must not be the delivery manager')
            if position['plan_step_id']:
                planned=self.db.execute("""
                   SELECT assignee_id FROM ago_plan_steps
                   WHERE tenant_id=%s AND plan_id=%s AND id=%s
                """,(actor.tenant_id,project['plan_id'],position['plan_step_id'])).fetchone()
                if planned and str(planned['assignee_id'])!=assignee_id:
                    raise PermissionError('Existing governed step must not be silently reassigned')
            existing=self.db.execute("""
                SELECT a.proposal_id,a.assignee_id
                FROM ago_project_stage_delegation_activations a
                WHERE a.tenant_id=%s AND a.intake_id=%s AND a.stage=%s
            """,(actor.tenant_id,project_id,stage)).fetchone()
            if existing:
                raise PermissionError('Stage already delegated; revisions require new governed policy')
            prior=self.db.execute("""
                SELECT d.id,d.approval_id,a.status
                FROM ago_project_stage_delegation_proposals d
                JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id
                   AND a.id=d.approval_id
                WHERE d.tenant_id=%s AND d.intake_id=%s AND d.stage=%s
                  AND d.assignee_id=%s AND a.status='pending'
                ORDER BY d.created_at DESC LIMIT 1
            """,(actor.tenant_id,project_id,stage,assignee_id)).fetchone()
            if prior:
                return {'proposal_id':str(prior['id']),
                        'approval_id':str(prior['approval_id']),
                        'status':'pending_founder_decision','reused':True,
                        'task_executed':False}
            proposal_id=str(uuid4())
            approval=self.repositories.resolve(ApprovalRepository).propose(
                tenant_id=actor.tenant_id,
                action='company:stage-delegation:'+proposal_id,
                requester_id=actor.subject,
            )
            self.db.execute("""
                INSERT INTO ago_project_stage_delegation_proposals
                   (id,tenant_id,intake_id,stage,assignee_id,requester_id,approval_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,(proposal_id,actor.tenant_id,project_id,stage,
                 assignee_id,actor.subject,approval.request_id))
        return {'proposal_id':proposal_id,'approval_id':approval.request_id,
                'status':'pending_founder_decision','stage':stage,
                'worker_name':worker['name'],'reused':False,'task_executed':False}

    def activate_stage_delegation(self, actor, project_id: str,
                                   proposal_id: str) -> dict:
        """Apply one approved stage owner. Never launches models, tools or tasks."""
        from uuid import uuid4
        UUID(actor.tenant_id)
        UUID(project_id)
        UUID(proposal_id)
        if 'founder' not in actor.roles:
            raise PermissionError('Human founder must apply reviewed personnel decisions')
        with self.db.transaction():
            project=self.db.execute("""
                SELECT i.id,i.plan_id,p.status
                FROM ago_founder_intakes i JOIN ago_strategy_plans p
                  ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
                WHERE i.tenant_id=%s AND i.id=%s FOR UPDATE OF i
            """,(actor.tenant_id,project_id)).fetchone()
            if project is None:
                raise LookupError('Project unavailable')
            proposed=self.db.execute("""
                SELECT d.*,a.status AS approval_status,a.reviewer_id,e.name AS worker_name
                FROM ago_project_stage_delegation_proposals d
                JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id AND a.id=d.approval_id
                JOIN ago_employees e ON e.tenant_id=d.tenant_id AND e.id=d.assignee_id
                WHERE d.tenant_id=%s AND d.id=%s AND d.intake_id=%s
            """,(actor.tenant_id,proposal_id,project_id)).fetchone()
            if proposed is None:
                raise LookupError('Matching reviewed proposal not found')
            existing=self.db.execute("""
                SELECT id,proposal_id FROM ago_project_stage_delegation_activations
                WHERE tenant_id=%s AND intake_id=%s AND stage=%s
            """,(actor.tenant_id,project_id,proposed['stage'])).fetchone()
            if existing:
                if str(existing['proposal_id'])!=proposal_id:
                    raise PermissionError('Stage already assigned by another approved proposal')
                return {'id':str(existing['id']),'stage':proposed['stage'],
                        'assignee_id':str(proposed['assignee_id']),
                        'reused':True,'task_executed':False}
            if project['status']!='active':
                raise PermissionError('Founder strategic plan must be approved and active')
            # The local single-founder exception must still be in force when
            # the reviewed stage assignment is actually activated, not only
            # when its approval row was originally written. Never replay this
            # exception after environment or active human authority changes.
            if (proposed['reviewer_id'] is not None
                    and str(proposed['reviewer_id'])==str(proposed['requester_id'])
                    and not founder_solo_eligible(
                        self.db, actor.tenant_id, actor.subject
                    )):
                raise PermissionError(
                    'Local sole-founder approval is not eligible for stage activation'
                )
            self.repositories.resolve(ApprovalRepository).assert_executable(
                request_id=str(proposed['approval_id']),tenant_id=actor.tenant_id,
                action='company:stage-delegation:'+proposal_id,
            )
            activation_id=str(uuid4())
            self.db.execute("""
                INSERT INTO ago_project_stage_delegation_activations
                  (id,tenant_id,proposal_id,intake_id,stage,assignee_id,applied_by)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """,(activation_id,actor.tenant_id,proposal_id,project_id,
                 proposed['stage'],proposed['assignee_id'],actor.subject))
            self.db.execute("""
                INSERT INTO ago_company_chat
                  (tenant_id,channel,author_id,author_name,body,kind,employee_id)
                VALUES (%s,'global',%s,'Company Brain',%s,'project',%s)
            """,(actor.tenant_id,actor.subject,
                 'Authorized reviewed project stage assignment: '+
                 proposed['stage']+' → '+proposed['worker_name']+
                 '; approved task execution remains separate.',
                 proposed['assignee_id']))
        return {'id':activation_id,'stage':proposed['stage'],
                'assignee_id':str(proposed['assignee_id']),
                'reused':False,'task_executed':False}

    def project_delegations(self, tenant_id: str, project_id: str,
                            reader_id: str | None = None) -> list[dict]:
        UUID(tenant_id)
        UUID(project_id)
        if reader_id is None:
            raise PermissionError('Authenticated project reader required')
        UUID(reader_id)
        available=self.db.execute("""
            SELECT 1 FROM ago_founder_intakes i
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
              AND l.intake_id=i.id
            WHERE i.tenant_id=%s AND i.id=%s
              AND (i.founder_id=%s OR l.accountable_manager_id=%s
                OR EXISTS(
                  SELECT 1 FROM ago_project_stage_delegation_activations a
                  WHERE a.tenant_id=i.tenant_id AND a.intake_id=i.id
                    AND a.assignee_id=%s
                ))
        """,(tenant_id,project_id,reader_id,reader_id,reader_id)).fetchone()
        if available is None:
            raise LookupError('Project unavailable')
        return [dict(r) for r in self.db.execute("""
            SELECT d.id,d.stage,d.assignee_id,e.name AS worker_name,
                   a.status AS approval_status,d.approval_id,d.created_at,
                   v.applied_at,v.applied_by
            FROM ago_project_stage_delegation_proposals d
            JOIN ago_approval_requests a ON a.tenant_id=d.tenant_id
              AND a.id=d.approval_id
            JOIN ago_employees e ON e.tenant_id=d.tenant_id AND e.id=d.assignee_id
            LEFT JOIN ago_project_stage_delegation_activations v
              ON v.tenant_id=d.tenant_id AND v.proposal_id=d.id
            WHERE d.tenant_id=%s AND d.intake_id=%s
            ORDER BY d.created_at,d.id
        """,(tenant_id,project_id)).fetchall()]

    def approval_inbox(self, tenant_id: str, limit: int = 100,
                       reader_id: str | None = None) -> list[dict]:
        """Persisted approvals with explicit founder-only localhost routing."""
        UUID(tenant_id)
        if not 1 <= limit <= 100:
            raise ValueError("Invalid approval inbox limit")
        rows = self.db.execute("""
            SELECT a.id,a.action,a.status,a.requester_id,a.reviewer_id,
                   a.reason,a.created_at,a.decided_at,
                   COALESCE(requester.name,'Unknown requester') AS requester_name,
                   requester.role_title AS requester_role,
                   manager.name AS requester_manager_name,
                   COALESCE(reviewer.name,'Not yet decided') AS reviewer_name,
                   EXISTS (
                     SELECT 1 FROM ago_project_stage_delegation_proposals stage_d
                     JOIN ago_founder_intakes stage_i
                       ON stage_i.tenant_id=stage_d.tenant_id
                       AND stage_i.id=stage_d.intake_id
                     WHERE stage_d.tenant_id=a.tenant_id
                       AND a.action=('company:stage-delegation:' || stage_d.id::text)
                       AND a.requester_id=stage_i.founder_id
                   ) AS founder_stage_scope,
                   p.id AS plan_id,p.title AS plan_title,
                   left(g.description,3000) AS goal_brief_excerpt,
                   i.id AS founder_intake_id,
                   t.id AS task_id,t.action AS task_action,t.status AS task_status,
                   t.assignee_id AS task_assignee_id,
                   assignee.name AS task_assignee_name,
                   COALESCE(d.name,td.name) AS department_name,
                   o.id AS opportunity_id,o.title AS opportunity_title,
                   o.target_customer AS opportunity_customer,
                   o.proposed_offer AS opportunity_offer,
                   o.revenue_path AS opportunity_revenue,
                   o.validation_next_step AS opportunity_validation,
                   signal.id AS market_signal_id,signal.title AS market_signal_title,
                   signal.source_url AS market_signal_url,
                   signal.source_name AS market_signal_source,
                   signal.source_kind AS market_signal_kind,
                   signal.potential_customer AS market_signal_customer,
                   signal.score_basis AS market_signal_score_basis,
                   signal.opportunity_score AS market_signal_score
            FROM ago_approval_requests a
            LEFT JOIN ago_employees requester
              ON requester.tenant_id=a.tenant_id AND requester.id=a.requester_id
            LEFT JOIN ago_departments d
              ON d.tenant_id=requester.tenant_id AND d.id=requester.department_id
            LEFT JOIN ago_employees manager
              ON manager.tenant_id=requester.tenant_id AND manager.id=requester.manager_id
            LEFT JOIN ago_employees reviewer
              ON reviewer.tenant_id=a.tenant_id AND reviewer.id=a.reviewer_id
            LEFT JOIN ago_strategy_plans p
              ON p.tenant_id=a.tenant_id AND p.approval_id=a.id
             AND a.action=('brain:activate:' || p.id::text)
            LEFT JOIN ago_goals g ON g.tenant_id=p.tenant_id AND g.id=p.goal_id
            LEFT JOIN ago_founder_intakes i ON i.tenant_id=p.tenant_id
             AND i.plan_id=p.id
            LEFT JOIN ago_governed_tasks t
              ON t.tenant_id=a.tenant_id AND t.approval_id=a.id
             AND t.action=a.action
            LEFT JOIN ago_company_opportunities o
              ON o.tenant_id=a.tenant_id AND o.approval_id=a.id
             AND a.action=('company:opportunity:' || o.id::text)
            LEFT JOIN ago_market_signals signal
              ON signal.tenant_id=a.tenant_id AND signal.approval_id=a.id
             AND a.action=('company:market-signal:' || signal.id::text)
            LEFT JOIN ago_employees assignee
              ON assignee.tenant_id=t.tenant_id AND assignee.id=t.assignee_id
            LEFT JOIN ago_departments td
              ON td.tenant_id=assignee.tenant_id AND td.id=assignee.department_id
            WHERE a.tenant_id=%s
            ORDER BY (a.status='pending') DESC,a.created_at DESC,a.id DESC
            LIMIT %s
        """, (tenant_id,limit)).fetchall()
        active_founder = bool(reader_id and founder_solo_eligible(self.db, tenant_id, reader_id))
        other_reviewer = self.db.execute("""
            SELECT 1 FROM ago_users u
            JOIN ago_employees e ON e.tenant_id=u.tenant_id
              AND e.id=u.id AND e.kind='human'
            JOIN ago_user_roles r ON r.tenant_id=u.tenant_id AND r.user_id=u.id
            JOIN ago_role_permissions p ON p.tenant_id=r.tenant_id
              AND p.role=r.role AND p.permission='approval:decide'
            WHERE u.tenant_id=%s AND u.active AND u.id<>%s LIMIT 1
        """, (tenant_id, reader_id)).fetchone() if active_founder else None
        solo = active_founder and other_reviewer is None
        result = []
        for row in rows:
            item = dict(row)
            item["approval_type"] = (
                "market_signal_review" if item["market_signal_id"] else
                "opportunity_review" if item["opportunity_id"] else
                "plan_review" if item["plan_id"] else
                "task_execution" if item["task_id"] else "governance_action"
            )
            strategic = bool(
                item["market_signal_id"] or item["opportunity_id"] or
                item["founder_intake_id"] or item["founder_stage_scope"]
            )
            item["requires_founder_decision"] = strategic
            item["founder_solo_mode"] = bool(
                solo and not strategic and
                item["action"] in ("internal:brief", "research:brief")
            )
            item["review_routing"] = (
                "Authenticated human Founder only: original approved strategic project scope"
                if strategic else
                "Founder may decide only narrowly allowed standalone internal work when no independent human reviewer exists; CEO verifies bounded approved-project tasks"
                if item["founder_solo_mode"] else
                "Independent active human review of ordinary operations; CEO verifies bounded Founder-approved project tasks"
            )
            item["next_action"] = (
                "Founder approval permits market validation and a governed project plan. No autonomous sales, email campaigns, ad spend or release is authorized."
                if item["opportunity_id"] or item["market_signal_id"] else
                "An approved plan requires separate activation and per-task approvals."
                if item["plan_id"] else
                "An approved task still requires explicit governed execution and QA."
                if item["task_id"] else
                "Only the exact approved action may be reconciled through its governed workflow."
            )
            result.append(item)
        return result

    def management_workload(self, tenant_id: str) -> dict:
        """Read actual assigned work and management accountability; never invent tasks."""
        UUID(tenant_id)
        employees = self.db.execute("""
            SELECT e.id,e.name,e.kind,e.role_title,e.manager_id,
                COUNT(DISTINCT t.id) FILTER (WHERE t.status='running') AS running,
                COUNT(DISTINCT t.id) FILTER (WHERE t.status IN
                    ('proposed','waiting_approval','ready')) AS queued,
                COUNT(DISTINCT t.id) FILTER (WHERE t.status='failed') AS failed,
                COUNT(DISTINCT t.id) FILTER (WHERE t.status='completed') AS completed,
                COUNT(DISTINCT q.task_id) FILTER (WHERE q.verdict='pass') AS qa_passed,
                COUNT(DISTINCT q.task_id) FILTER (WHERE q.verdict='fail') AS qa_failed,
                COUNT(DISTINCT t.id) FILTER (WHERE t.status='completed' AND q.id IS NULL) AS unreviewed,
                COUNT(DISTINCT t.id) FILTER (
                     WHERE t.management_escalation_required) AS leadership_gaps,
                COUNT(DISTINCT p.intake_id) AS projects_accountable
            FROM ago_employees e
            LEFT JOIN ago_governed_tasks t ON t.tenant_id=e.tenant_id
                AND t.assignee_id=e.id
            LEFT JOIN ago_founder_project_lead p ON p.tenant_id=e.tenant_id
                AND p.accountable_manager_id=e.id
            LEFT JOIN ago_task_reviews q ON q.tenant_id=t.tenant_id
                AND q.task_id=t.id
            WHERE e.tenant_id=%s
            GROUP BY e.id,e.name,e.kind,e.role_title,e.manager_id
            ORDER BY e.name,e.id
        """, (tenant_id,)).fetchall()
        leaders = self.db.execute("""
            SELECT t.accountable_manager_id,e.name AS manager_name,
                COUNT(*) AS governed_actions,
                COUNT(*) FILTER (WHERE t.status IN ('proposed','waiting_approval','ready')) AS awaiting_work
            FROM ago_governed_tasks t JOIN ago_employees e
                ON e.tenant_id=t.tenant_id AND e.id=t.accountable_manager_id
            WHERE t.tenant_id=%s
            GROUP BY t.accountable_manager_id,e.name ORDER BY e.name
        """,(tenant_id,)).fetchall()
        vacancies = self.db.execute("""
            SELECT i.id AS project_id,i.title AS project_title,s.stage,s.deliverable,
                   l.accountable_manager_id,owner.name AS responsible_manager_name
            FROM ago_founder_intake_stages s
            JOIN ago_founder_intakes i ON i.tenant_id=s.tenant_id AND i.id=s.intake_id
            JOIN ago_founder_project_lead l ON l.tenant_id=i.tenant_id
                 AND l.intake_id=i.id
            JOIN ago_employees owner ON owner.tenant_id=l.tenant_id
                 AND owner.id=l.accountable_manager_id
            WHERE s.tenant_id=%s AND s.suggested_assignee_id IS NULL
            ORDER BY i.created_at,s.position LIMIT 50
        """,(tenant_id,)).fetchall()
        counts = [dict(e) for e in employees]
        # Skill-based staffing recommendations are READ-ONLY. No fictitious hire,
        # reassignment, approval or agent execution is manufactured.
        skill_map = {
            'discovery':('research','analyst','product'),
            'architecture':('architect','technical lead','cto'),
            'implementation':('developer','engineer','programmer'),
            'quality':('quality','qa','tester'),
            'release':('devops','release','operations','delivery'),
        }
        candidate_rows = self.db.execute("""
            SELECT id,name,kind,role_title FROM ago_employees WHERE tenant_id=%s
        """,(tenant_id,)).fetchall()
        work_index={str(e['id']):e for e in counts}
        proposed = []
        for v in vacancies:
            target=dict(v)
            terms=skill_map.get(v['stage'],())
            matches=[
                e for e in candidate_rows if e['kind']=='ai'
                and any(term in (e['name']+' '+(e['role_title'] or '')).lower()
                        for term in terms)
                and not (v['stage']=='quality'
                         and str(e['id'])==str(v['accountable_manager_id']))
            ]
            matches.sort(key=lambda e:(
                int(work_index[str(e['id'])]['running'])+int(work_index[str(e['id'])]['queued']),
                str(e['id'])))
            top=matches[0] if matches else None
            target['candidate_id']=str(top['id']) if top else None
            target['candidate_name']=top['name'] if top else None
            target['candidate_workload']=(
                int(work_index[str(top['id'])]['running'])+int(work_index[str(top['id'])]['queued'])
                if top else None)
            target['recommendation']='qualified_existing_worker' if top else 'review_staffing_gap'
            target['founder_local_qa_candidate']=False
            proposed.append(target)
        return {
            'employees':counts,
            'leaders':[dict(leader_row) for leader_row in leaders],
            'unassigned_project_stages':proposed,
            'qa_passed_count':sum(int(e['qa_passed']) for e in counts),
            'qa_failed_count':sum(int(e['qa_failed']) for e in counts),
            'awaiting_qa_count':sum(int(e['unreviewed']) for e in counts),
            'recommended_placements':sum(v['candidate_id'] is not None for v in proposed),
            'staffing_decisions_executed':0,
            'review_recommendations':(
                (['Review failed QA evidence and open scoped corrective tasks.']
                 if any(int(e['qa_failed'])>0 for e in counts) else []) +
                (['Obtain independent QA for completed governed work before release.']
                 if any(int(e['unreviewed'])>0 for e in counts) else []) +
                (['Management should review qualified existing staff or governed recruitment requests.']
                 if proposed else []) +
                (['Evaluate recorded market hypotheses and customer validation evidence.']
                 if counts and all(not (e['running'] or e['queued']) for e in counts) else [])
            ),
            'recommendations_are_advisory':True,
            'idle_employees':sum(e['running']==0 and e['queued']==0 for e in counts),
            'pending_employee_work':sum(int(e['queued']) for e in counts),
            'unmanaged_task_alerts':sum(int(e['leadership_gaps']) for e in counts),
            'unassigned_work_generated':False,
            'note':'Idle means no recorded running or queued governed task, not employee inactivity. Only authorized, useful work should be assigned.',
        }

    def market_intelligence(self, tenant_id: str, limit: int = 100) -> dict:
        """Tenant-scoped factual signals, CEO-ranked leads and unpublished campaign drafts."""
        UUID(tenant_id)
        if not 1 <= limit <= 200:
            raise ValueError('Invalid market intelligence limit')
        signals = self.db.execute("""
            SELECT s.id,s.source_name,s.source_kind,s.source_url,s.title,s.excerpt,
                   s.potential_customer,s.opportunity_score,s.score_basis,
                   s.evidence_level,s.review_status,s.discovery_method,s.discovered_at,
                   s.published_at,s.nominated_at,s.approval_id,a.status AS approval_status,
                   e.name AS executive_owner_name,
                   linked.intake_id AS linked_project_id
            FROM ago_market_signals s
            LEFT JOIN ago_approval_requests a ON a.tenant_id=s.tenant_id
               AND a.id=s.approval_id
            LEFT JOIN ago_employees e ON e.tenant_id=s.tenant_id
               AND e.id=s.executive_owner_id
            LEFT JOIN ago_market_signal_project_links linked ON linked.tenant_id=s.tenant_id
               AND linked.signal_id=s.id
            WHERE s.tenant_id=%s
            ORDER BY (s.review_status='shortlisted') DESC,
                     s.opportunity_score DESC,s.discovered_at DESC,s.id
            LIMIT %s
        """,(tenant_id,limit)).fetchall()
        drafts = self.db.execute("""
            SELECT m.id,m.project_id,i.title AS project_title,m.platform,
                   m.draft_text,m.stage,m.external_post_url,m.approval_id,m.created_at
            FROM ago_marketing_drafts m
            JOIN ago_founder_intakes i ON i.tenant_id=m.tenant_id AND i.id=m.project_id
            WHERE m.tenant_id=%s
            ORDER BY m.created_at DESC,m.id LIMIT %s
        """,(tenant_id,limit)).fetchall()
        scans = self.db.execute("""
            SELECT source_name,outcome,ingested_count,checked_at,error_class
            FROM ago_growth_scan_runs WHERE tenant_id=%s
            ORDER BY checked_at DESC,id DESC LIMIT 12
        """,(tenant_id,)).fetchall()
        total = self.db.execute("""
            SELECT COUNT(*) AS total FROM ago_market_signals WHERE tenant_id=%s
        """,(tenant_id,)).fetchone()['total']
        return {
            'signals':[dict(row) for row in signals],
            'signal_total':total,
            'marketing_drafts':[dict(row) for row in drafts],
            'source_health':[dict(row) for row in scans],
            'claimed_verified_revenue':False,
            'external_posting_configured':False,
            'note':'RSS items are unvalidated hypotheses. Heuristic ranking is not proof of demand. '
                   'CEO-accountable nomination requires founder review; social posts are drafts only.',
        }

    @staticmethod
    def _opportunity_catalog() -> tuple[tuple[str, ...], ...]:
        """Seed hypotheses only; no claim of AI research or customer interviews."""
        return (
            ('admission_followup','Admission follow-up setup for training institutes',
             'Independent coaching and training institutes',
             'Inbound inquiries get lost across calls and spreadsheets',
             'Lead capture, counselling follow-up and weekly admission reports',
             'Paid setup plus optional monthly maintenance',
             'Interview three institute owners and test willingness to pay'),
            ('local_services_crm','Customer and appointment follow-up for local services',
             'Small repair, tutoring and appointment-based businesses',
             'Inquiries and booked appointments are not consistently followed up',
             'Enquiry intake, opt-in appointment reminders and simple reporting',
             'Paid onboarding followed by a support retainer only after a pilot',
             'Interview five businesses and obtain customer contact consent'),
            ('assessment_reports','Assessment and reporting service for institutes',
             'Independent training centres and vocational institutes',
             'Progress reports and evaluations create repetitive admin work',
             'Instructor-reviewed assessment and progress-report workflows',
             'Pilot delivery fee, then a verified subscription offer',
             'Validate instructor requirements, privacy needs and budget'),
        )

    def opportunity_radar(self, tenant_id: str, limit: int = 30) -> list[dict]:
        UUID(tenant_id)
        if not 1 <= limit <= 100:
            raise ValueError('Invalid opportunity limit')
        return [dict(row) for row in self.db.execute("""
            SELECT o.id,o.cycle_start,o.catalog_key,o.title,o.target_customer,
                   o.customer_problem,o.proposed_offer,o.revenue_path,
                   o.validation_next_step,o.accountable_manager_id,
                   e.name AS accountable_manager_name,o.assignment_source,
                   o.discovery_type,o.approval_id,a.status AS approval_status,
                   a.reason AS approval_reason,o.created_at
            FROM ago_company_opportunities o
            JOIN ago_approval_requests a ON a.tenant_id=o.tenant_id
              AND a.id=o.approval_id
            JOIN ago_employees e ON e.tenant_id=o.tenant_id
              AND e.id=o.accountable_manager_id
            WHERE o.tenant_id=%s
            ORDER BY o.created_at DESC,o.catalog_key LIMIT %s
        """,(tenant_id,limit)).fetchall()]

    def scan_opportunities(self, tenant_id: str) -> dict:
        """Monthly idempotent idle-work suggestions, never outside transactions."""
        from uuid import uuid4
        UUID(tenant_id)
        created=[]
        with self.db.transaction():
            tenant=self.db.execute(
                'SELECT id FROM ago_tenants WHERE id=%s FOR UPDATE',
                (tenant_id,)).fetchone()
            if tenant is None:
                raise LookupError('Company not found')
            founder=self.db.execute("""
                SELECT e.id FROM ago_employees e
                JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id AND u.active
                JOIN ago_user_roles r ON r.tenant_id=e.tenant_id AND r.user_id=e.id
                WHERE e.tenant_id=%s AND r.role='founder' AND e.kind='human'
                ORDER BY e.id LIMIT 1
            """,(tenant_id,)).fetchone()
            if founder is None:
                return {'created':0,'reason':'no_active_founder','opportunities':[]}
            executives=self.db.execute("""
                SELECT id,name,role_title FROM ago_employees
                WHERE tenant_id=%s ORDER BY
                CASE
                  WHEN lower(trim(coalesce(role_title,''))) IN
                       ('ceo','chief executive officer') OR lower(name)='ceo' THEN 0
                  WHEN lower(trim(coalesce(role_title,''))) IN
                       ('coo','chief operating officer') THEN 1
                  WHEN lower(trim(coalesce(role_title,''))) IN
                       ('cto','chief technology officer') THEN 2
                  ELSE 99 END,id
            """,(tenant_id,)).fetchall()
            executive=next((e for e in executives
                      if (e['role_title'] or '').strip().lower()
                         in ('ceo','chief executive officer','coo',
                             'chief operating officer','cto','chief technology officer')
                      or e['name'].strip().lower()=='ceo'),None)
            owner=executive['id'] if executive else founder['id']
            assignment='executive_manager' if executive else 'founder_escalation'
            work=self.db.execute("""
                SELECT 1 FROM ago_governed_tasks
                WHERE tenant_id=%s AND status='running' LIMIT 1
            """,(tenant_id,)).fetchone()
            if work:
                return {'created':0,'reason':'delivery_running','opportunities':[]}
            for key,title,customer,problem,offer,revenue,validation in self._opportunity_catalog():
                prior=self.db.execute("""
                    SELECT id FROM ago_company_opportunities WHERE tenant_id=%s
                      AND cycle_start=date_trunc('month',now())::date AND catalog_key=%s
                """,(tenant_id,key)).fetchone()
                if prior:
                    continue
                opportunity_id=str(uuid4())
                action='company:opportunity:'+opportunity_id
                # Governance owns all protected approval/audit writes.
                # The real executive is an accountability owner; the idea is
                # explicitly labeled as automatically catalog-generated.
                proposal=self.repositories.resolve(ApprovalRepository).propose(
                    tenant_id=tenant_id,action=action,requester_id=str(owner))
                approval_id=proposal.request_id
                self.db.execute("""
                    INSERT INTO ago_company_opportunities
                     (id,tenant_id,cycle_start,catalog_key,title,target_customer,
                      customer_problem,proposed_offer,revenue_path,validation_next_step,
                      accountable_manager_id,assignment_source,approval_id)
                    VALUES (%s,%s,date_trunc('month',now())::date,
                            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,(opportunity_id,tenant_id,key,title,customer,problem,
                     offer,revenue,validation,owner,assignment,approval_id))
                created.append({'id':opportunity_id,'title':title})
        return {'created':len(created),
                'reason':'idle_hypotheses_proposed' if created else 'already_proposed_this_month',
                'opportunities':created}
