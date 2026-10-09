"""M5: deterministic organizational risk simulation; never mutates production state."""
from __future__ import annotations

from decimal import Decimal

from ago.credits import credits


class ScenarioSimulator:
    @staticmethod
    def estimate(
        *, planned_actions: int, cost_per_action,
        available_credits, failure_percent: int = 0,
    ) -> dict:
        if not 0 <= planned_actions <= 1_000_000:
            raise ValueError("Invalid planned action count")
        if not 0 <= failure_percent <= 100:
            raise ValueError("Invalid failure rate")
        unit_cost = credits(cost_per_action)
        available = Decimal(str(available_credits))
        if not available.is_finite() or available < 0:
            raise ValueError("Invalid available credits")
        projected = unit_cost * planned_actions
        expected_failures = (
            Decimal(planned_actions) * Decimal(failure_percent) / Decimal(100)
        )
        risks = []
        if projected > available:
            risks.append("budget_shortfall")
        if failure_percent >= 30:
            risks.append("high_failure_rate")
        return {
            "planned_actions": planned_actions,
            "projected_credit_use": str(projected),
            "available_credits": str(available),
            "expected_failures": str(expected_failures),
            "risk_flags": risks,
            "simulation_only": True,
        }
