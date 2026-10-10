# Section 1 — Complete Source Module Inventory

Generated from the Section 14 contract. All imports are checked against source.
Regenerate only after a reviewed policy change; this file grants no permission.

| Module | Organizational context | Registered layer | Permitted imports |
|---|---|---|---|
| [__init__](../../apps/backend/ago/__init__.py) | entrypoints | composition | None |
| [access](../../apps/backend/ago/access.py) | governance | foundation | security |
| [agent_handlers](../../apps/backend/ago/agent_handlers.py) | workforce | service | workflows |
| [agent_runtime](../../apps/backend/ago/agent_runtime.py) | workforce | service | task_store |
| [api_agents](../../apps/backend/ago/api_agents.py) | transport | transport | agent_handlers, agent_runtime, api_m2, model_handlers, security |
| [api_brain](../../apps/backend/ago/api_brain.py) | transport | transport | api_m2, goals, plan_execution, plan_store, security |
| [api_council](../../apps/backend/ago/api_council.py) | transport | transport | api_m2, council_store, security |
| [api_insights](../../apps/backend/ago/api_insights.py) | transport | transport | api_m2, credits, experiments, scorecard, security, simulation |
| [api_knowledge](../../apps/backend/ago/api_knowledge.py) | transport | transport | api_m2, knowledge_store, security |
| [api_m2](../../apps/backend/ago/api_m2.py) | transport | transport | governance, governed_execution, identity, login_security, memory, organization_store, quality, quality_store, security, security_controls, task_store |
| [api_meta](../../apps/backend/ago/api_meta.py) | transport | transport | api_m2, executive_intelligence, meta_brain, organizational_dna, security |
| [api_operations](../../apps/backend/ago/api_operations.py) | transport | transport | api_m2, calendar_store, handoffs, security |
| [api_tools](../../apps/backend/ago/api_tools.py) | transport | transport | api_m2, department_automation, security, tool_catalog, tool_enrollment, tool_runtime |
| [approvals](../../apps/backend/ago/approvals.py) | governance | domain | None |
| [architecture_guard](../../apps/backend/ago/architecture_guard.py) | entrypoints | foundation | None |
| [auth_api](../../apps/backend/ago/auth_api.py) | transport | transport | rate_limit, security |
| [auth_guard](../../apps/backend/ago/auth_guard.py) | transport | transport | security |
| [bootstrap](../../apps/backend/ago/bootstrap.py) | entrypoints | composition | identity, organization_store, security_controls |
| [calendar_store](../../apps/backend/ago/calendar_store.py) | operations | persistence | security |
| [console_api](../../apps/backend/ago/console_api.py) | transport | transport | api_m2, governance, security, security_controls, task_store |
| [console_host](../../apps/backend/ago/console_host.py) | transport | transport | None |
| [council_store](../../apps/backend/ago/council_store.py) | governance | persistence | governance, security, security_controls |
| [credits](../../apps/backend/ago/credits.py) | economics | domain | None |
| [department_automation](../../apps/backend/ago/department_automation.py) | operations | service | governance, security, task_store, tool_catalog, tool_enrollment |
| [event_contracts](../../apps/backend/ago/event_contracts.py) | platform | domain | events |
| [event_migrations](../../apps/backend/ago/event_migrations.py) | platform | foundation | None |
| [event_runtime](../../apps/backend/ago/event_runtime.py) | entrypoints | composition | event_migrations, event_worker, events, postgres_event_store |
| [event_store](../../apps/backend/ago/event_store.py) | platform | persistence | events |
| [event_worker](../../apps/backend/ago/event_worker.py) | platform | service | events |
| [events](../../apps/backend/ago/events.py) | platform | domain | None |
| [execution](../../apps/backend/ago/execution.py) | workforce | service | security, workflows |
| [executive_intelligence](../../apps/backend/ago/executive_intelligence.py) | strategy | service | organizational_dna |
| [experiments](../../apps/backend/ago/experiments.py) | strategy | domain | governance |
| [feature_flags](../../apps/backend/ago/feature_flags.py) | platform | foundation | None |
| [goals](../../apps/backend/ago/goals.py) | strategy | domain | None |
| [governance](../../apps/backend/ago/governance.py) | governance | domain | approvals |
| [governed_execution](../../apps/backend/ago/governed_execution.py) | governance | service | governance, security, security_controls, workflows |
| [handoffs](../../apps/backend/ago/handoffs.py) | operations | persistence | security, security_controls |
| [identity](../../apps/backend/ago/identity.py) | governance | persistence | security |
| [knowledge_store](../../apps/backend/ago/knowledge_store.py) | knowledge | persistence | security, security_controls |
| [local_ops](../../apps/backend/ago/local_ops.py) | entrypoints | composition | bootstrap, provision, release_security |
| [login_security](../../apps/backend/ago/login_security.py) | governance | persistence | None |
| [m6_permissions](../../apps/backend/ago/m6_permissions.py) | entrypoints | composition | security_controls |
| [m7_permissions](../../apps/backend/ago/m7_permissions.py) | entrypoints | composition | security_controls |
| [m8_permissions](../../apps/backend/ago/m8_permissions.py) | entrypoints | composition | security_controls |
| [main](../../apps/backend/ago/main.py) | entrypoints | composition | api_agents, api_brain, api_council, api_insights, api_knowledge, api_m2, api_meta, api_operations, api_tools, console_api, console_host, platform, readiness, release_security |
| [memory](../../apps/backend/ago/memory.py) | knowledge | domain | None |
| [meta_brain](../../apps/backend/ago/meta_brain.py) | strategy | service | executive_intelligence, governance |
| [metrics](../../apps/backend/ago/metrics.py) | platform | foundation | None |
| [model_handlers](../../apps/backend/ago/model_handlers.py) | workforce | service | credits, model_provider |
| [model_provider](../../apps/backend/ago/model_provider.py) | workforce | foundation | None |
| [organization](../../apps/backend/ago/organization.py) | workforce | domain | None |
| [organization_store](../../apps/backend/ago/organization_store.py) | workforce | persistence | memory, organization |
| [organizational_dna](../../apps/backend/ago/organizational_dna.py) | strategy | domain | governance |
| [plan_execution](../../apps/backend/ago/plan_execution.py) | strategy | service | governance, task_store |
| [plan_store](../../apps/backend/ago/plan_store.py) | strategy | persistence | governance |
| [platform](../../apps/backend/ago/platform.py) | platform | foundation | events |
| [plugins](../../apps/backend/ago/plugins.py) | platform | foundation | None |
| [postgres_event_store](../../apps/backend/ago/postgres_event_store.py) | platform | persistence | events |
| [provision](../../apps/backend/ago/provision.py) | entrypoints | composition | identity, security_controls |
| [quality](../../apps/backend/ago/quality.py) | governance | domain | None |
| [quality_store](../../apps/backend/ago/quality_store.py) | governance | persistence | quality, security, security_controls |
| [rate_limit](../../apps/backend/ago/rate_limit.py) | governance | foundation | None |
| [readiness](../../apps/backend/ago/readiness.py) | platform | foundation | None |
| [release_ops](../../apps/backend/ago/release_ops.py) | entrypoints | composition | release_security |
| [release_security](../../apps/backend/ago/release_security.py) | platform | composition | event_runtime |
| [scheduler](../../apps/backend/ago/scheduler.py) | platform | foundation | None |
| [scorecard](../../apps/backend/ago/scorecard.py) | economics | service | credits |
| [security](../../apps/backend/ago/security.py) | governance | domain | None |
| [security_controls](../../apps/backend/ago/security_controls.py) | governance | persistence | security |
| [simulation](../../apps/backend/ago/simulation.py) | strategy | service | credits |
| [task_store](../../apps/backend/ago/task_store.py) | workforce | persistence | security, security_controls, workflows |
| [tool_catalog](../../apps/backend/ago/tool_catalog.py) | operations | service | scorecard |
| [tool_enrollment](../../apps/backend/ago/tool_enrollment.py) | operations | service | governance, security, tool_catalog |
| [tool_runtime](../../apps/backend/ago/tool_runtime.py) | operations | service | security_controls, task_store, tool_catalog, tool_enrollment |
| [workflows](../../apps/backend/ago/workflows.py) | workforce | domain | None |
