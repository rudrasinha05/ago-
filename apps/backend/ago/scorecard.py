"""M5: privacy-preserving tenant-only operational scorecard."""
from ago.credits import CreditBudget


class Scorecard:
    def __init__(self, db):
        self.db = db

    def summary(self, *, tenant_id: str) -> dict:
        counts = {}
        entities = {
            "goals": "ago_goals",
            "plans": "ago_strategy_plans",
            "tasks": "ago_governed_tasks",
            "agent_runs": "ago_agent_runs",
            "qa_reviews": "ago_task_reviews",
            "experiments": "ago_policy_experiments",
            "handoffs": "ago_handoffs",
            "calendar_events": "ago_calendar_events",
            "knowledge_nodes": "ago_knowledge_nodes",
            "council_motions": "ago_council_motions",
        }
        # SQL identifiers come exclusively from trusted server-owned constants.
        for label, table in entities.items():
            row = self.db.execute(
                f"SELECT count(*) AS total FROM {table} WHERE tenant_id=%s",
                (tenant_id,),
            ).fetchone()
            counts[label] = int(row["total"])
        tasks = self.db.execute(
            """SELECT status,count(*) AS total FROM ago_governed_tasks
               WHERE tenant_id=%s GROUP BY status""",
            (tenant_id,),
        ).fetchall()
        return {
            "counts": counts,
            "task_status": {row["status"]: int(row["total"]) for row in tasks},
            "virtual_credit_budget": CreditBudget(self.db).balance(tenant_id=tenant_id),
        }
