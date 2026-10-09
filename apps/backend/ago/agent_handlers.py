"""Built-in deterministic handler. Real model/provider integration is opt-in."""
from ago.workflows import GovernedTask


def internal_brief(task: GovernedTask) -> dict:
    if task.action != "internal:brief":
        raise PermissionError("Handler not allowed for action")
    return {
        "task_id": task.id,
        "kind": "internal_brief",
        "brief": "Internal review packet prepared for human QA.",
        "requires_human_qa": True,
    }


BUILTIN_HANDLERS = {"internal:brief": internal_brief}
