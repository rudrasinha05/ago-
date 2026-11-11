"""Evidence-first CEO supervision and routing for the existing Global Chat.

No model inference, role impersonation, approval, executable task creation or
release happens in this module. A system receipt is NOT an AI acknowledgement.
"""
from __future__ import annotations

import json
import re
from uuid import UUID, uuid4

# At most ten explicitly addressed employees. Zero mentions means CEO default
# for every Founder message; so a question also gets a truthful receipt.
MAX_ADDRESSEES = 10
BRACED_TAG = re.compile(r"@\{([^{}]{1,80})\}")


class GlobalChatOrders:
    def __init__(self, db):
        self.db = db

    @staticmethod
    def _uuid(value):
        try:
            return str(UUID(str(value)))
        except (ValueError, AttributeError, TypeError) as exc:
            raise ValueError("Unknown or malformed employee mention") from exc

    def _employees(self, tenant_id):
        rows = self.db.execute("""
            SELECT id,name,kind,manager_id FROM ago_employees
            WHERE tenant_id=%s ORDER BY id
        """, (tenant_id,)).fetchall()
        return {str(r["id"]): dict(r) for r in rows}

    def resolve_mentions(self, tenant_id, body, supplied=()):
        """Stable UUID mentions or unique @display names, NEVER loose substring IDs."""
        employees = self._employees(tenant_id)
        values = [self._uuid(x) for x in supplied]
        for inner in BRACED_TAG.findall(body):
            values.append(self._uuid(inner))
        if "@{" in body and len(BRACED_TAG.findall(body)) != body.count("@{"):
            raise ValueError("Malformed structured employee mention")
        # Human-friendly @Full Employee Name; ambiguity is a hard error. These
        # are not a privilege grant; target identity must belong to this tenant.
        for match in re.finditer(r"(?<![\w@])@([\w][\w .-]{0,150})", body):
            fragment = match.group(1)
            choices = [
                (ident, row["name"]) for ident, row in employees.items()
                if (fragment.casefold().startswith(row["name"].casefold())
                    and (len(fragment) == len(row["name"]) or
                         fragment[len(row["name"])] in " .,!?;:\n"))
            ]
            if not choices:
                continue  # ordinary @text is not evidence of an assignee
            longest = max(len(name) for _, name in choices)
            candidates = [ident for ident, name in choices if len(name) == longest]
            if len(candidates) != 1:
                raise ValueError("Ambiguous @employee name; select a unique UUID")
            values.append(candidates[0])
        distinct = sorted(set(values))
        if len(distinct) > MAX_ADDRESSEES:
            raise ValueError("At most ten employees may be mentioned per message")
        if any(ident not in employees for ident in distinct):
            raise ValueError("Mentioned employee is not in this company")
        return distinct, employees

    def _ceo(self, tenant_id, employees):
        row = self.db.execute("""
            SELECT e.id,e.name FROM ago_company_board_appointments b
            JOIN ago_employees e ON e.tenant_id=b.tenant_id AND e.id=b.employee_id
            WHERE b.tenant_id=%s AND b.seat='Strategy & Vision' AND e.kind='ai'
        """,(tenant_id,)).fetchone()
        return (dict(row) if row and str(row["id"]) in employees else None)

    def route(self, *, tenant_id, author_id, message_id, body, mentions=(),
              intent="message", founder=False):
        """Idempotently register every Founder global message and explicit tags.

        Called from CompanyChat.send in the SAME database transaction. A
        pending work item does NOT mean an AI agent saw or accepted the order.
        """
        if intent not in ("message","order"):
            raise ValueError("Unknown chat intent")
        if intent == "order" and not founder:
            raise PermissionError("Only the founder may issue company-wide orders")
        addresses, employees = self.resolve_mentions(tenant_id,body,mentions)
        if not founder and not addresses:
            return None
        previous = self.db.execute("""
            SELECT intent,mention_ids,founder_order,accountable_ceo_id,
                   state,receipt_message_id FROM ago_chat_orders
            WHERE tenant_id=%s AND message_id=%s
        """,(tenant_id,message_id)).fetchone()
        if previous:
            if (previous["intent"] != intent or
                    sorted(previous["mention_ids"]) != addresses or
                    previous["founder_order"] != founder):
                raise ValueError("Retry key cannot change an existing order route")
            return self.details(tenant_id,message_id)
        ceo = self._ceo(tenant_id,employees)
        ceo_id = str(ceo["id"]) if ceo else None
        state = "awaiting_ack" if ceo_id else "blocked_no_ceo"
        self.db.execute("""
            INSERT INTO ago_chat_orders
              (tenant_id,message_id,founder_order,accountable_ceo_id,
               intent,mention_ids,state)
            VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s)
        """,(tenant_id,message_id,founder,ceo_id,intent,
             json.dumps(addresses),state))
        recipients = sorted(set(addresses + ([ceo_id] if ceo_id else [])))
        if ceo_id:
            for emp_id in recipients:
                self.db.execute("""
                    INSERT INTO ago_chat_work_items
                      (id,tenant_id,message_id,assignee_id,accountable_ceo_id)
                    VALUES (%s,%s,%s,%s,%s)
                """,(str(uuid4()),tenant_id,message_id,emp_id,ceo_id))
        if ceo_id:
            target_names = ", ".join(employees[i]["name"] for i in recipients
                                     if i != ceo_id)
            suffix = (f" Assigned specialists: {target_names}." if target_names
                      else " CEO is the default responsible recipient.")
            receipt = (f"AGO system receipt for message #{message_id}: recorded "
                       f"as {intent}. Appointed AI CEO {ceo['name']} is accountable."
                       + suffix +
                       " Acknowledgements and governed actions are PENDING; "
                       "no AI reply, task execution or approval has been claimed.")
        else:
            receipt = (f"AGO system receipt for message #{message_id}: recorded "
                       "but BLOCKED. No appointed AI CEO is available to own "
                       "the work. Founder must appoint an eligible AI CEO. "
                       "No employee acknowledgement or execution is claimed.")
        row = self.db.execute("""
            INSERT INTO ago_company_chat
             (tenant_id,channel,author_name,body,reply_to,kind,employee_id)
            VALUES (%s,'global','AGO system · order intake',%s,%s,'status',%s)
            RETURNING id
        """,(tenant_id,receipt,message_id,ceo_id)).fetchone()
        self.db.execute("""
            UPDATE ago_chat_orders SET receipt_message_id=%s
            WHERE tenant_id=%s AND message_id=%s
        """,(row["id"],tenant_id,message_id))
        return self.details(tenant_id,message_id)

    def details(self, tenant_id, message_id):
        order = self.db.execute("""
            SELECT message_id,founder_order,accountable_ceo_id,intent,mention_ids,
                   receipt_message_id,state,created_at FROM ago_chat_orders
            WHERE tenant_id=%s AND message_id=%s
        """,(tenant_id,message_id)).fetchone()
        if order is None:
            return None
        workers = self.db.execute("""
            SELECT w.id,w.assignee_id,e.name AS assignee_name,w.accountable_ceo_id,
                   w.status,w.linked_task_id,w.ack_message_id,w.updated_at
            FROM ago_chat_work_items w
            JOIN ago_employees e ON e.tenant_id=w.tenant_id AND e.id=w.assignee_id
            WHERE w.tenant_id=%s AND w.message_id=%s ORDER BY e.name,w.id
        """,(tenant_id,message_id)).fetchall()
        return {**dict(order),"work_items":[dict(x) for x in workers],
                "verified_acknowledgements":sum(
                    w["ack_message_id"] is not None for w in workers),
                "system_receipt_only":True}

    def record_human_acknowledgement(self, *, tenant_id, actor_id,
                                     parent_id, response_id):
        """Only the actual signed human addressee's reply counts as acknowledgement.

        No virtual AI employee is considered to have replied through a human
        login. A system receipt has author_id=NULL and can never enter here.
        """
        if parent_id is None:
            return False
        verified = self.db.execute("""
            UPDATE ago_chat_work_items w
            SET status=CASE WHEN w.linked_task_id IS NULL THEN 'acknowledged'
                            ELSE 'task_linked' END,
                ack_message_id=%s,updated_at=now()
            FROM ago_employees e
            WHERE w.tenant_id=%s AND w.message_id=%s AND w.assignee_id=%s
              AND e.tenant_id=w.tenant_id AND e.id=w.assignee_id
              AND e.kind='human' AND w.ack_message_id IS NULL
            RETURNING w.id
        """,(response_id,tenant_id,parent_id,actor_id)).fetchone()
        return verified is not None

    def attach(self, *, tenant_id, actor_id, actor_is_founder, message_id,
               employee_id, task_id):
        """Link only a REAL existing, same-tenant task to the chat order.

        No automatic approval, execution, counterfeit CEO acknowledgement,
        or cross-project task fabrication. Exact employee matches task owner.
        """
        employee_id = self._uuid(employee_id)
        task_id = self._uuid(task_id)
        with self.db.transaction():
            work = self.db.execute("""
                SELECT id,status,linked_task_id FROM ago_chat_work_items
                WHERE tenant_id=%s AND message_id=%s AND assignee_id=%s
                FOR UPDATE
            """,(tenant_id,message_id,employee_id)).fetchone()
            if work is None:
                raise ValueError("No routed work item for this order and employee")
            if not actor_is_founder and actor_id != employee_id:
                raise PermissionError("Only founder or the actual assignee can link evidence")
            task = self.db.execute("""
                SELECT id,status,assignee_id,action FROM ago_governed_tasks
                WHERE tenant_id=%s AND id=%s
            """,(tenant_id,task_id)).fetchone()
            if task is None or str(task["assignee_id"]) != employee_id:
                raise PermissionError("Task must exist and belong to the tagged employee")
            if work["linked_task_id"]:
                if str(work["linked_task_id"]) != task_id:
                    raise PermissionError("Work item is already linked to a different task")
            else:
                self.db.execute("""
                    UPDATE ago_chat_work_items
                    SET linked_task_id=%s,status='task_linked',updated_at=now()
                    WHERE id=%s AND tenant_id=%s
                """,(task_id,work["id"],tenant_id))
            return {"message_id":message_id,"employee_id":employee_id,
                    "task_id":task_id,"task_status":task["status"],
                    "verified_task_link":True,"ai_acknowledged":False,
                    "task_executed_by_chat":False}
