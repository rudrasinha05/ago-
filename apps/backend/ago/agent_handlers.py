"""Built-in deterministic handler. Real model/provider integration is opt-in."""
from ago.workflows import GovernedTask


def internal_brief(task: GovernedTask) -> dict:
    if task.action != "internal:brief":
        raise PermissionError("Handler not allowed for action")
    if task.project_context:
        project = task.project_context
        return {
            "task_id": task.id,
            "kind": "founder_scope_packet",
            "intake_id": project["intake_id"],
            "title": project["title"],
            "founder_brief_excerpt": project["brief"][:1800],
            "proposed_checklist": [
                "Validate user stories and measurable acceptance criteria",
                "Review architecture, dependencies and data permissions",
                "Approve engineering milestones and staffed responsibilities",
                "Verify tests, documentation, accessibility and security",
                "Obtain independent QA and owner release approval",
            ],
            "scope_status": "review_required",
            "code_written": False,
            "github_pushed": False,
            "requires_human_qa": True,
        }
    result = {
        "task_id": task.id,
        "kind": "internal_brief",
        "brief": "Internal review packet prepared for human QA.",
        "requires_human_qa": True,
    }
    if task.experiment_context:
        result["experiment"] = dict(task.experiment_context)
        if task.experiment_context["variant"] == "candidate":
            result["review_checklist"] = ["Verify task authorization", "Inspect deliverable", "Record independent QA evidence"]
        else:
            result["review_notes"] = "Verify authorization, inspect deliverable and record independent QA evidence."
    return result


BUILTIN_HANDLERS = {"internal:brief": internal_brief}
