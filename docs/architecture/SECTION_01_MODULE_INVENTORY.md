# Section 1 — Complete Source Module Inventory

Generated from the Section 14 contract. All imports are checked against source.
Regenerate only after a reviewed policy change; this file grants no permission.

| Module | Organizational context | Registered layer | Permitted imports |
|---|---|---|---|
| [__init__](../../apps/backend/ago/__init__.py) | entrypoints | composition | None |
| [access](../../apps/backend/ago/access.py) | governance | persistence | backend_contracts, security |
| [agent_handlers](../../apps/backend/ago/agent_handlers.py) | workforce | service | workflows |
| [agent_runtime](../../apps/backend/ago/agent_runtime.py) | workforce | service | agent_runtime_queries, backend_contracts, organizational_dna, task_store |
| [agent_runtime_queries](../../apps/backend/ago/agent_runtime_queries.py) | workforce | persistence | backend_contracts |
| [api_agents](../../apps/backend/ago/api_agents.py) | transport | transport | agent_handlers, api_m2, backend_contracts, model_handlers, repository_ports, security |
| [api_brain](../../apps/backend/ago/api_brain.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security |
| [api_contracts](../../apps/backend/ago/api_contracts.py) | transport | transport | None |
| [api_council](../../apps/backend/ago/api_council.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security |
| [api_insights](../../apps/backend/ago/api_insights.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security, simulation |
| [api_knowledge](../../apps/backend/ago/api_knowledge.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security, storage_adapters |
| [api_m2](../../apps/backend/ago/api_m2.py) | transport | transport | api_contracts, backend_contracts, governed_execution, memory, quality, repository_ports, security, security_material |
| [api_meta](../../apps/backend/ago/api_meta.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security |
| [api_operations](../../apps/backend/ago/api_operations.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security |
| [api_tools](../../apps/backend/ago/api_tools.py) | transport | transport | api_contracts, api_m2, backend_contracts, repository_ports, security, tool_catalog |
| [approvals](../../apps/backend/ago/approvals.py) | governance | domain | None |
| [architecture_guard](../../apps/backend/ago/architecture_guard.py) | entrypoints | foundation | None |
| [auth_api](../../apps/backend/ago/auth_api.py) | transport | transport | api_contracts, rate_limit, security |
| [auth_guard](../../apps/backend/ago/auth_guard.py) | transport | transport | security |
| [backend_contracts](../../apps/backend/ago/backend_contracts.py) | platform | foundation | None |
| [bootstrap](../../apps/backend/ago/bootstrap.py) | entrypoints | composition | identity, organization_store, security_controls |
| [calendar_store](../../apps/backend/ago/calendar_store.py) | operations | persistence | backend_contracts, security |
| [console_api](../../apps/backend/ago/console_api.py) | transport | transport | api_m2, backend_contracts, repository_ports, security |
| [console_host](../../apps/backend/ago/console_host.py) | transport | transport | None |
| [console_service](../../apps/backend/ago/console_service.py) | governance | service | backend_contracts, console_store, governance, security, task_store |
| [console_store](../../apps/backend/ago/console_store.py) | governance | persistence | backend_contracts, security |
| [council_store](../../apps/backend/ago/council_store.py) | governance | persistence | backend_contracts, governance, security, security_controls |
| [credit_domain](../../apps/backend/ago/credit_domain.py) | economics | domain | None |
| [credits](../../apps/backend/ago/credits.py) | economics | persistence | backend_contracts, credit_domain |
| [database_store](../../apps/backend/ago/database_store.py) | knowledge | persistence | backend_contracts, security, storage_adapters |
| [department_automation](../../apps/backend/ago/department_automation.py) | operations | service | backend_contracts, department_automation_queries, governance, security, task_store, tool_catalog, tool_enrollment |
| [department_automation_queries](../../apps/backend/ago/department_automation_queries.py) | operations | persistence | backend_contracts |
| [dna_domain](../../apps/backend/ago/dna_domain.py) | strategy | domain | None |
| [enterprise_domains](../../apps/backend/ago/enterprise_domains.py) | operations | domain | None |
| [enterprise_store](../../apps/backend/ago/enterprise_store.py) | operations | persistence | backend_contracts, enterprise_domains, security |
| [event_contracts](../../apps/backend/ago/event_contracts.py) | platform | domain | events |
| [event_migrations](../../apps/backend/ago/event_migrations.py) | platform | foundation | None |
| [event_runtime](../../apps/backend/ago/event_runtime.py) | entrypoints | composition | event_migrations, event_worker, events, postgres_event_store |
| [event_store](../../apps/backend/ago/event_store.py) | platform | persistence | events |
| [event_worker](../../apps/backend/ago/event_worker.py) | platform | service | events |
| [events](../../apps/backend/ago/events.py) | platform | domain | None |
| [execution](../../apps/backend/ago/execution.py) | workforce | service | security, workflows |
| [executive_intelligence](../../apps/backend/ago/executive_intelligence.py) | strategy | service | architecture_guard, backend_contracts, executive_intelligence_queries, organizational_dna |
| [executive_intelligence_queries](../../apps/backend/ago/executive_intelligence_queries.py) | strategy | persistence | backend_contracts |
| [experiments](../../apps/backend/ago/experiments.py) | strategy | persistence | backend_contracts, governance |
| [feature_flags](../../apps/backend/ago/feature_flags.py) | platform | foundation | None |
| [goals](../../apps/backend/ago/goals.py) | strategy | persistence | backend_contracts |
| [governance](../../apps/backend/ago/governance.py) | governance | persistence | approvals, backend_contracts, governance_domain |
| [governance_domain](../../apps/backend/ago/governance_domain.py) | governance | domain | approvals |
| [governed_execution](../../apps/backend/ago/governed_execution.py) | governance | service | governance, security, security_controls, workflows |
| [handoffs](../../apps/backend/ago/handoffs.py) | operations | persistence | backend_contracts, security, security_controls |
| [http_errors](../../apps/backend/ago/http_errors.py) | transport | transport | None |
| [identity](../../apps/backend/ago/identity.py) | governance | persistence | backend_contracts, security |
| [identity_factors](../../apps/backend/ago/identity_factors.py) | governance | foundation | security |
| [identity_security_store](../../apps/backend/ago/identity_security_store.py) | governance | persistence | backend_contracts, identity, identity_factors, login_security, security, security_controls, sso_provider |
| [knowledge_store](../../apps/backend/ago/knowledge_store.py) | knowledge | persistence | backend_contracts, security, security_controls |
| [local_ops](../../apps/backend/ago/local_ops.py) | entrypoints | composition | bootstrap, provision, release_ops, release_security |
| [login_security](../../apps/backend/ago/login_security.py) | governance | persistence | backend_contracts |
| [m6_permissions](../../apps/backend/ago/m6_permissions.py) | entrypoints | composition | security_controls |
| [m7_permissions](../../apps/backend/ago/m7_permissions.py) | entrypoints | composition | security_controls |
| [m8_permissions](../../apps/backend/ago/m8_permissions.py) | entrypoints | composition | security_controls |
| [main](../../apps/backend/ago/main.py) | entrypoints | composition | api_agents, api_brain, api_council, api_insights, api_knowledge, api_m2, api_meta, api_operations, api_tools, console_api, console_host, http_errors, platform, readiness, release_security, security_material |
| [memory](../../apps/backend/ago/memory.py) | knowledge | domain | None |
| [memory_policies](../../apps/backend/ago/memory_policies.py) | knowledge | domain | None |
| [message_contracts](../../apps/backend/ago/message_contracts.py) | platform | domain | None |
| [message_ops](../../apps/backend/ago/message_ops.py) | entrypoints | composition | backend_contracts, message_store |
| [message_store](../../apps/backend/ago/message_store.py) | platform | persistence | backend_contracts, message_contracts, security, security_controls |
| [meta_brain](../../apps/backend/ago/meta_brain.py) | strategy | service | backend_contracts, executive_intelligence, governance, meta_brain_queries, organizational_dna |
| [meta_brain_queries](../../apps/backend/ago/meta_brain_queries.py) | strategy | persistence | backend_contracts |
| [metrics](../../apps/backend/ago/metrics.py) | platform | foundation | None |
| [model_handlers](../../apps/backend/ago/model_handlers.py) | workforce | service | backend_contracts, credits, model_provider |
| [model_provider](../../apps/backend/ago/model_provider.py) | workforce | foundation | None |
| [organization](../../apps/backend/ago/organization.py) | workforce | domain | None |
| [organization_store](../../apps/backend/ago/organization_store.py) | workforce | persistence | backend_contracts, memory, organization |
| [organizational_dna](../../apps/backend/ago/organizational_dna.py) | strategy | persistence | backend_contracts, dna_domain, governance |
| [plan_execution](../../apps/backend/ago/plan_execution.py) | strategy | service | backend_contracts, governance, plan_execution_queries, task_store |
| [plan_execution_queries](../../apps/backend/ago/plan_execution_queries.py) | strategy | persistence | backend_contracts |
| [plan_store](../../apps/backend/ago/plan_store.py) | strategy | persistence | backend_contracts, governance |
| [platform](../../apps/backend/ago/platform.py) | platform | foundation | events |
| [plugins](../../apps/backend/ago/plugins.py) | platform | foundation | None |
| [postgres_event_store](../../apps/backend/ago/postgres_event_store.py) | platform | persistence | events |
| [provision](../../apps/backend/ago/provision.py) | entrypoints | composition | identity, security_controls |
| [quality](../../apps/backend/ago/quality.py) | governance | domain | None |
| [quality_store](../../apps/backend/ago/quality_store.py) | governance | persistence | backend_contracts, quality, security, security_controls |
| [rate_limit](../../apps/backend/ago/rate_limit.py) | governance | foundation | None |
| [readiness](../../apps/backend/ago/readiness.py) | platform | foundation | None |
| [release_ops](../../apps/backend/ago/release_ops.py) | entrypoints | composition | release_security, security_material |
| [release_security](../../apps/backend/ago/release_security.py) | platform | composition | event_runtime, identity_factors, security_material, sso_provider |
| [repository_ports](../../apps/backend/ago/repository_ports.py) | platform | service | access, agent_runtime, agent_runtime_queries, approvals, backend_contracts, calendar_store, console_service, console_store, council_store, credits, database_store, department_automation, department_automation_queries, executive_intelligence, executive_intelligence_queries, experiments, goals, governance, handoffs, identity, identity_security_store, knowledge_store, login_security, memory, message_store, meta_brain, meta_brain_queries, organization, organization_store, organizational_dna, plan_execution, plan_execution_queries, plan_store, quality, quality_store, scorecard, scorecard_queries, security, security_controls, semantic_memory_store, session_service, task_store, tool_catalog_queries, tool_enrollment, tool_enrollment_queries, tool_runtime, tool_runtime_queries, workflows |
| [scheduler](../../apps/backend/ago/scheduler.py) | platform | foundation | None |
| [scorecard](../../apps/backend/ago/scorecard.py) | economics | service | backend_contracts, credits, scorecard_queries |
| [scorecard_queries](../../apps/backend/ago/scorecard_queries.py) | economics | persistence | backend_contracts |
| [security](../../apps/backend/ago/security.py) | governance | domain | None |
| [security_controls](../../apps/backend/ago/security_controls.py) | governance | persistence | backend_contracts, security |
| [security_material](../../apps/backend/ago/security_material.py) | platform | foundation | security |
| [semantic_memory_store](../../apps/backend/ago/semantic_memory_store.py) | knowledge | persistence | backend_contracts, memory_policies, security, security_controls, storage_adapters |
| [session_service](../../apps/backend/ago/session_service.py) | governance | service | backend_contracts, identity, identity_security_store, login_security, security |
| [simulation](../../apps/backend/ago/simulation.py) | strategy | service | credits |
| [sso_provider](../../apps/backend/ago/sso_provider.py) | governance | foundation | security, security_material |
| [storage_adapters](../../apps/backend/ago/storage_adapters.py) | platform | foundation | None |
| [storage_ops](../../apps/backend/ago/storage_ops.py) | entrypoints | composition | backend_contracts, database_store, storage_adapters |
| [task_store](../../apps/backend/ago/task_store.py) | workforce | persistence | backend_contracts, security, security_controls, workflows |
| [tool_catalog](../../apps/backend/ago/tool_catalog.py) | operations | service | backend_contracts, scorecard, tool_catalog_queries |
| [tool_catalog_queries](../../apps/backend/ago/tool_catalog_queries.py) | operations | persistence | backend_contracts |
| [tool_enrollment](../../apps/backend/ago/tool_enrollment.py) | operations | service | backend_contracts, governance, security, tool_catalog, tool_enrollment_queries |
| [tool_enrollment_queries](../../apps/backend/ago/tool_enrollment_queries.py) | operations | persistence | backend_contracts |
| [tool_runtime](../../apps/backend/ago/tool_runtime.py) | operations | service | backend_contracts, security_controls, task_store, tool_catalog, tool_enrollment, tool_runtime_queries |
| [tool_runtime_queries](../../apps/backend/ago/tool_runtime_queries.py) | operations | persistence | backend_contracts |
| [workflows](../../apps/backend/ago/workflows.py) | workforce | domain | None |
