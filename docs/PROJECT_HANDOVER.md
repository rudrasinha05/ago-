# AGO — Project Handover and Continuity

## Purpose
Artificial General Organization (AGO) is a governed, persistent AI-native enterprise operating system. The founder defines goals; organizational AI agents operate through hierarchical departments, managers, workers, testers and auditors, with persistent organizational memory and human approval for consequential actions.

## Approved Architecture
The previously drafted AI Company Enterprise Architecture Blueprint comprises Sections 0–35, covering the Company Brain, Meta Brain, Corporate Constitution, Organizational DNA, Executive Council, Organizational Operating System (OOS), departments, AI employees, workflow orchestration, tool execution, QA/testing, independent audit, memory, knowledge graph, economics, marketplace, analytics, digital twin, organizational calendar, API platform, and security. AGO research ambitions include organizational self-design, adaptation, genome-inspired organization policies, fitness evaluation, and evolutionary experiments. Those research directions are future scope, not implemented capabilities.

## Development Rules (BDR)
- Preserve the approved modular-monolith-first architecture and milestone roadmap; no unsolicited plan changes.
- Work on a single `develop` branch for implementation when it is available; do not create many feature branches.
- Make implementation modular, type-checked, testable, documented, and production-conscious.
- Do not mark features complete based only on generated text. Record actual test commands and outcomes.
- Independent audit and hardening gates precede the next milestone.
- Do not silently overwrite or replace already-developed local work.
- Report actual state, unresolved blockers, and evidence accurately.

## Historical Progress — User/Codex Reported (NOT GitHub Verified)
- Enterprise architecture documentation: Sections 0–35 drafted.
- M0 Repository Foundation: reported complete.
- M0.1 Foundation Hardening: reported complete (report indicated some Docker and CI checks were unverified).
- M1.1 Enterprise Configuration Platform: reported complete.
- M1.2 Enterprise Logging Platform: reported complete.
- M1.3 Enterprise Dependency Injection Platform: prompt issued; completion not yet verified.

These milestones were worked on with Codex and VS Code before this repository was connected. Their source code has not been migrated here as of this document's creation. Do not infer presence of any module from this historical status.

## Locked Next Milestone Sequence
M1.3 Dependency Injection Platform → M1.4 Event Bus → M1.5 Authentication → M1.6 RBAC → M1.7 Plugin Framework → M1.8 Scheduler → M1.9 Health and Observability → Core Platform Audit. Further organizational subsystems follow the approved blueprint's dependency order. Avoid modifying this sequence without founder approval.

## Migration Requirements
1. Obtain the full existing local Codex/VS Code project or authoritative repository and its latest verified commit.
2. Preserve tracked files, architecture spec, tests, lockfiles, Docker configuration and reports exactly, subject to secret-scanning and necessary path normalization.
3. Compare the source against the target repository before any migration.
4. Import through reviewed commits on the designated implementation branch.
5. Run tests and report successes/failures before continuing M1.3/M1.4.

## Safety and Provenance
Keep API keys, .env files, credentials, and proprietary secrets out of commits. The project is not release-ready merely because its architecture is extensive. Approval for deployments, spending, external communications, access expansions, and destructive operations stays with authorized humans.
