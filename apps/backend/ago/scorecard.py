"""M5: privacy-preserving tenant-only operational scorecard."""

from __future__ import annotations

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.credits import CreditBudget
from ago.scorecard_queries import ScorecardQueries


class Scorecard:
    def __init__(self, db: DatabaseConnection, *, repositories: RepositoryScope | None = None):
        self.db = db
        self.repositories = repositories or RepositoryScope(db)

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
            "dna_versions": "ago_dna_versions",
            "executive_snapshots": "ago_executive_snapshots",
            "meta_recommendations": "ago_meta_recommendations",
            "tool_enrollments": "ago_tool_enrollments",
            "automation_rules": "ago_automation_rules",
            "automation_firings": "ago_automation_firings",
            "tool_runs": "ago_tool_runs",
        }
        # SQL identifiers come exclusively from trusted server-owned constants.
        for label, table in entities.items():
            row = (
                self.repositories.resolve(ScorecardQueries)
                .select_tenant_count_01((tenant_id,), table=table)
                .fetchone()
            )
            counts[label] = int(row["total"])
        tasks = (
            self.repositories.resolve(ScorecardQueries)
            .select_ago_governed_tasks_02((tenant_id,))
            .fetchall()
        )
        return {
            "counts": counts,
            "task_status": {row["status"]: int(row["total"]) for row in tasks},
            "virtual_credit_budget": self.repositories.resolve(CreditBudget).balance(
                tenant_id=tenant_id
            ),
        }
