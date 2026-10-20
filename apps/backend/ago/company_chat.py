"""Tenant-visible company conversations. Channels are filters, never private DMs."""
from __future__ import annotations
from uuid import UUID
from dataclasses import asdict
from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.organization_store import OrganizationStore


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

    def list(self, tenant, channel, before, limit):
        self.channel(tenant, channel)
        # A department includes its employee conversations and task events.
        rows = self.db.execute('''SELECT c.*, parent.body AS reply_body, parent.author_name AS reply_author FROM ago_company_chat c LEFT JOIN ago_company_chat parent ON parent.tenant_id=c.tenant_id AND parent.id=c.reply_to
          WHERE c.tenant_id=%s AND (%s='global' OR c.channel=%s OR
            (%s LIKE 'department:%%' AND c.employee_id IN
              (SELECT id FROM ago_employees WHERE tenant_id=%s AND department_id::text=substring(%s from 12))))
          AND (%s::bigint IS NULL OR c.id < %s)
          ORDER BY c.id DESC LIMIT %s''',
          (tenant, channel, channel, channel, tenant, channel, before, before, limit+1)).fetchall()
        return {'items': list(reversed(rows[:limit])),
                'next_before': rows[limit-1]['id'] if len(rows)>limit else None}

    def send(self, actor, channel, body, reply_to, operation_key):
        self.channel(actor.tenant_id, channel)
        body = body.strip()
        if not body:
            raise ValueError('Write a message first')
        with self.db.transaction():
            if reply_to is not None and not self.db.execute(
                'SELECT id FROM ago_company_chat WHERE tenant_id=%s AND id=%s',
                (actor.tenant_id, reply_to),
            ).fetchone():
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
            return row

    def activity(self, tenant_id):
        return self.db.execute('''SELECT t.*, p.title AS project_name,
      p.id AS plan_id FROM ago_governed_tasks t
      LEFT JOIN ago_plan_steps s ON s.tenant_id=t.tenant_id AND s.task_id=t.id
      LEFT JOIN ago_strategy_plans p ON p.tenant_id=s.tenant_id AND p.id=s.plan_id
      WHERE t.tenant_id=%s ORDER BY t.updated_at DESC''', (tenant_id,)).fetchall()

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

    def notifications(self, tenant_id: str) -> dict:
        """Persistent work-event counts, excluding ordinary chat messages.

        Includes task transitions and authenticated upward reports.
        The latest event ID is safe for incremental browser polling.
        """
        rows = self.db.execute("""
            SELECT e.id AS employee_id, COUNT(c.id) AS event_count
            FROM ago_employees e
            LEFT JOIN ago_company_chat c ON c.tenant_id=e.tenant_id
              AND c.employee_id=e.id AND c.kind IN ('status','report','staffing','github','qa','docs','project')
            WHERE e.tenant_id=%s
            GROUP BY e.id ORDER BY e.id
        """, (tenant_id,)).fetchall()
        recent = self.db.execute("""
            SELECT id, employee_id, task_id, body, kind, created_at
            FROM ago_company_chat
            WHERE tenant_id=%s AND kind IN ('status','report','staffing','github','qa','docs','project')
            ORDER BY id DESC LIMIT 100
        """, (tenant_id,)).fetchall()
        return {
            "by_employee": {str(row["employee_id"]): int(row["event_count"]) for row in rows},
            "recent": [dict(row) for row in recent],
            "event_type": "committed_work_event",
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
                    SELECT id,name,kind,role_title,department_id FROM ago_employees
                    WHERE tenant_id=%s ORDER BY name,id
                """, (actor.tenant_id,)).fetchall()
                reviewer_rows = self.db.execute("""
                    SELECT e.id FROM ago_employees e
                    JOIN ago_user_roles ur ON ur.tenant_id=e.tenant_id AND ur.user_id=e.id
                    JOIN ago_users u ON u.tenant_id=e.tenant_id AND u.id=e.id
                    WHERE e.tenant_id=%s AND e.kind='human' AND u.active
                      AND ur.role='reviewer'
                """, (actor.tenant_id,)).fetchall()
                reviewers = {str(r['id']) for r in reviewer_rows}
                available_ai = [e for e in employees if e['kind']=='ai']
                discovery = next((e for e in available_ai
                                  if any(term in (e['name']+' '+(e['role_title'] or '')).lower()
                                         for term in ('research','analyst','product'))),None)
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
                    ('quality','Record independent QA, failure evidence and release blockers',
                     ('quality','qa','tester','reviewer'), 'reviewer'),
                    ('release','Prepare GitHub review package and owner release decision',
                     ('devops','release','operations','delivery'), 'ai'),
                )
                for index, (stage, deliverable, keywords, required_kind) in enumerate(stages,1):
                    if stage == 'discovery':
                        assignee = discovery
                    elif required_kind == 'reviewer':
                        assignee = next((e for e in employees if str(e['id']) in reviewers),None)
                    else:
                        assignee = next((e for e in available_ai
                                         if any(keyword in
                                                (e['name']+' '+(e['role_title'] or '')).lower()
                                                for keyword in keywords)),None)
                    self.db.execute("""
                        INSERT INTO ago_founder_intake_stages
                        (tenant_id,intake_id,plan_id,position,stage,deliverable,suggested_assignee_id,plan_step_id)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (actor.tenant_id,intake_id,plan_id,index,stage,deliverable,
                          assignee['id'] if assignee else None,
                          first_step if stage=='discovery' else None))
                # Notify founder without pretending the staff started work.
                self.db.execute("""
                    INSERT INTO ago_company_chat
                    (tenant_id,channel,author_id,author_name,body,kind,employee_id)
                    VALUES (%s,'global',%s,'Founder','Project intake saved: ' || %s,
                            'project',%s)
                """, (actor.tenant_id,actor.subject,title,actor.subject))
                reused = False

            row = self.db.execute("""
                SELECT i.id,i.title,i.goal_id,i.plan_id,i.created_at,p.status AS plan_status
                FROM ago_founder_intakes i JOIN ago_strategy_plans p
                  ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
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

    def projects(self, tenant_id: str, limit: int = 30) -> list[dict]:
        UUID(tenant_id)
        if not 1 <= limit <= 50:
            raise ValueError('Invalid project history limit')
        return [dict(row) for row in self.db.execute("""
            SELECT i.id,i.title,i.goal_id,i.plan_id,i.created_at,p.status AS plan_status,
              (SELECT COUNT(*) FROM ago_founder_intake_stages s
               WHERE s.tenant_id=i.tenant_id AND s.intake_id=i.id
                 AND s.suggested_assignee_id IS NULL) AS staffing_gaps,
              (SELECT COALESCE(json_agg(json_build_object(
                  'stage',s.stage,'deliverable',s.deliverable,
                  'suggested_assignee_name',e.name,
                  'suggested_role',e.role_title,'plan_step_id',s.plan_step_id
               ) ORDER BY s.position),'[]'::json)
               FROM ago_founder_intake_stages s
               LEFT JOIN ago_employees e
                 ON e.tenant_id=s.tenant_id AND e.id=s.suggested_assignee_id
               WHERE s.tenant_id=i.tenant_id AND s.intake_id=i.id) AS stages
            FROM ago_founder_intakes i JOIN ago_strategy_plans p
                 ON p.tenant_id=i.tenant_id AND p.id=i.plan_id
            WHERE i.tenant_id=%s ORDER BY i.created_at DESC,i.id DESC LIMIT %s
        """, (tenant_id,limit)).fetchall()]

    def approval_inbox(self, tenant_id: str, limit: int = 100) -> list[dict]:
        """Evidence-backed approvals, without inventing a designated reviewer.

        Actual approval:decide authority and independent-human checks are
        enforced by GovernanceGate at the existing decision endpoint.
        """
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
                   p.id AS plan_id,p.title AS plan_title,
                   left(g.description,3000) AS goal_brief_excerpt,
                   i.id AS founder_intake_id,
                   t.id AS task_id,t.action AS task_action,t.status AS task_status,
                   t.assignee_id AS task_assignee_id,
                   assignee.name AS task_assignee_name,
                   COALESCE(d.name,td.name) AS department_name
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
            LEFT JOIN ago_employees assignee
              ON assignee.tenant_id=t.tenant_id AND assignee.id=t.assignee_id
            LEFT JOIN ago_departments td
              ON td.tenant_id=assignee.tenant_id AND td.id=assignee.department_id
            WHERE a.tenant_id=%s
            ORDER BY (a.status='pending') DESC,a.created_at DESC,a.id DESC
            LIMIT %s
        """, (tenant_id,limit)).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["approval_type"] = (
                "plan_review" if item["plan_id"] else
                "task_execution" if item["task_id"] else "governance_action"
            )
            item["review_routing"] = (
                "Independent authorized human reviewer; not automatically assigned"
            )
            item["next_action"] = (
                "An approved plan requires separate activation and per-task approvals."
                if item["plan_id"] else
                "An approved task still requires explicit governed execution and QA."
                if item["task_id"] else
                "Only the exact approved action may be reconciled through its governed workflow."
            )
            result.append(item)
        return result
