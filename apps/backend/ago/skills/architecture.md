# Architecture skills

## arch.system-design
title: Design a software system
roles: cto, pm, employee
stages: architecture
keywords: architecture, design, system, component, module, diagram, scalability, service
source: AGO original (Claude, 2026-11-24)
---
1. Start from the users and the 3-5 core use cases. 2. List components and the single job of each. 3. Draw data flow: where data enters, is stored, leaves. 4. Pick the simplest design that meets today's scale (a modular monolith before microservices). 5. Name the risks: security, data loss, cost, vendor lock-in, and a mitigation each. 6. Define interfaces (APIs, events) before internals. 7. Record decisions and rejected options (ADR).

## arch.data-model
title: Data model for a product
roles: cto, employee
stages: architecture
keywords: data, model, entity, schema, relationship, table, fields, erd
source: AGO original (Claude, 2026-11-24)
---
1. List the nouns of the domain; each candidate is an entity. 2. For each: id, required fields, optional fields, valid values. 3. Relationships with cardinality (one-to-many etc.). 4. Who owns each record; tenant and privacy rules. 5. What history must be kept (audit, versions). 6. Indexes for the main queries. 7. Example records to check the model fits real cases.

## arch.adr
title: Architecture decision record
roles: cto, pm
stages: architecture
keywords: decision, adr, tradeoff, option, choice, rationale, record
source: AGO original (Claude, 2026-11-24)
---
Write: 1. Context: the problem and constraints. 2. Options considered (2-3) with pros and cons. 3. Decision and why it wins for us now. 4. Consequences: what gets easier, harder, what we must watch. 5. Status (proposed/accepted/replaced) and date. Keep it under one page; link it from the code area it affects.

## arch.mvp-scope
title: Scope a minimum viable product
roles: pm, cto, ceo
stages: discovery, architecture
keywords: mvp, scope, minimum, viable, product, first, version, prototype, launch
source: AGO original (Claude, 2026-11-24)
---
1. One primary user and one painful problem. 2. The single journey that solves it end to end. 3. Must-have features only for that journey; everything else goes to a later list. 4. Fake or manual what you can (concierge MVP). 5. Define success numbers before building. 6. Time-box to weeks, not months. 7. Plan how you will learn from the first users.

## arch.integration
title: Integrate with a third-party service
roles: cto, employee, risk
stages: architecture, implementation
keywords: integration, third-party, api, webhook, oauth, payment, external, service, sdk
source: AGO original (Claude, 2026-11-24)
---
1. Read the provider's limits, pricing and terms first. 2. Wrap the service behind one adapter module. 3. Store credentials in a secret store, never in code. 4. Timeouts, retries with backoff, and idempotency for writes. 5. Verify webhook signatures. 6. Plan for the provider being down: queue, fallback or clear error. 7. Test against the sandbox, then a small real call.
