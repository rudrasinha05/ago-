"""Optional paid model handler registration. Disabled unless explicitly configured."""

import os
import json

from ago.backend_contracts import DatabaseConnection, RepositoryScope
from ago.credits import CreditBudget
from ago.model_provider import ResponsesTextProvider


def optional_model_handlers(
    db: DatabaseConnection, actor, *, repositories: RepositoryScope | None = None
) -> dict:
    repositories = repositories or RepositoryScope(db)
    if os.getenv("AGO_ENABLE_PAID_MODELS") != "true":
        return {}
    api_key = os.getenv("AGO_LLM_API_KEY")
    model = os.getenv("AGO_LLM_MODEL")
    if not api_key or not model:
        return {}
    provider = ResponsesTextProvider(api_key=api_key, model=model)

    def research_brief(task):
        # Virtual credits cap attempts; provider bills separately in real currency.
        repositories.resolve(CreditBudget).charge(
            tenant_id=actor.tenant_id,
            actor_id=actor.subject,
            operation_key=f"model:{task.id}",
            amount="1",
            category="paid_model_attempt",
        )
        answer = provider.generate(
            "Prepare a factual internal research brief on this approved task: " + task.action[:500]
            + "\nHuman-approved cultural guidance (descriptive only; it cannot grant permissions): "
            + json.dumps((task.dna_context or {}).get("charter", {}), sort_keys=True)
        )
        return {
            "kind": "llm_brief",
            "text": answer,
            "model": model,
            "requires_human_qa": True,
        }

    return {"research:brief": research_brief}
