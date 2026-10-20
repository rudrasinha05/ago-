"""Tenant-visible company conversations. Channels are filters, never private DMs."""
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
            row = self.send(actor, channel, body, None, str(operation_key))
            db.execute("UPDATE ago_company_chat SET kind='staffing',employee_id=%s WHERE tenant_id=%s AND id=%s",
                       (employee.id, actor.tenant_id, row['id']))
            return asdict(employee)
