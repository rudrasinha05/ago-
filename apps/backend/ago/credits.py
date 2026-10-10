"""M5 transactionally bounded virtual-credit budget ledger.

Credits are internal accounting units, not real-world money or payments.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.credit_domain import credits as credits


class CreditBudget:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

    def configure(self, *, tenant_id: str, ceiling) -> None:
        UUID(tenant_id)
        cap = credits(ceiling)
        with self.db.transaction():
            self.db.execute(
                """INSERT INTO ago_credit_budgets(tenant_id,ceiling)
                   VALUES (%s,%s)
                   ON CONFLICT(tenant_id) DO UPDATE SET
                     ceiling=EXCLUDED.ceiling,updated_at=now()
                   WHERE ago_credit_budgets.consumed <= EXCLUDED.ceiling""",
                (tenant_id, cap),
            )
            row = self.db.execute(
                "SELECT ceiling FROM ago_credit_budgets WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
            if row is None or Decimal(row["ceiling"]) != cap:
                raise PermissionError("Cannot set ceiling below consumed credits")

    def charge(
        self, *, tenant_id: str, actor_id: str, operation_key: str, amount, category: str
    ) -> dict:
        UUID(tenant_id)
        UUID(actor_id)
        qty = credits(amount)
        if not operation_key.strip() or len(operation_key) > 180:
            raise ValueError("Invalid operation key")
        if not category.strip() or len(category) > 100:
            raise ValueError("Invalid usage category")
        with self.db.transaction():
            budget = self.db.execute(
                """SELECT ceiling,consumed FROM ago_credit_budgets
                   WHERE tenant_id=%s FOR UPDATE""",
                (tenant_id,),
            ).fetchone()
            if budget is None:
                raise PermissionError("No configured virtual-credit budget")
            existing = self.db.execute(
                """SELECT id,amount,category,actor_id
                   FROM ago_credit_usage
                   WHERE tenant_id=%s AND operation_key=%s""",
                (tenant_id, operation_key),
            ).fetchone()
            if existing:
                if (
                    Decimal(existing["amount"]) != qty
                    or existing["category"] != category
                    or str(existing["actor_id"]) != actor_id
                ):
                    raise PermissionError("Operation key cannot be reused differently")
                return {"id": str(existing["id"]), "charged": False}
            if Decimal(budget["consumed"]) + qty > Decimal(budget["ceiling"]):
                raise PermissionError("Virtual-credit budget exceeded")
            usage_id = str(uuid4())
            self.db.execute(
                """INSERT INTO ago_credit_usage
                   (id,tenant_id,operation_key,amount,category,actor_id)
                   VALUES (%s,%s,%s,%s,%s,%s)""",
                (usage_id, tenant_id, operation_key, qty, category, actor_id),
            )
            self.db.execute(
                """UPDATE ago_credit_budgets
                   SET consumed=consumed+%s,updated_at=now() WHERE tenant_id=%s""",
                (qty, tenant_id),
            )
            return {"id": usage_id, "charged": True}

    def balance(self, *, tenant_id: str) -> dict:
        row = self.db.execute(
            "SELECT ceiling,consumed FROM ago_credit_budgets WHERE tenant_id=%s",
            (tenant_id,),
        ).fetchone()
        if row is None:
            return {"ceiling": "0", "consumed": "0", "remaining": "0"}
        ceiling, consumed = Decimal(row["ceiling"]), Decimal(row["consumed"])
        return {
            "ceiling": str(ceiling),
            "consumed": str(consumed),
            "remaining": str(ceiling - consumed),
        }
