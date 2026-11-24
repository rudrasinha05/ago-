# DevOps and release skills

## ops.docker
title: Containerize an application
roles: employee, cto
stages: implementation, release
keywords: docker, container, image, dockerfile, compose, deploy
source: AGO original (Claude, 2026-11-24)
---
1. Small official base image with a pinned version. 2. Copy dependency files first, install, then copy code (layer cache). 3. Run as a non-root user. 4. No secrets in the image; pass them at runtime. 5. One process per container; a health check endpoint. 6. .dockerignore for build output and secrets. 7. Scan the image for vulnerabilities before release.

## ops.ci-pipeline
title: Continuous integration pipeline
roles: employee, cto, qa
stages: implementation, quality, release
keywords: ci, pipeline, github, actions, build, test, lint, workflow, automation
source: AGO original (Claude, 2026-11-24)
---
1. Run on every push and pull request. 2. Steps: install with lockfile, lint, type check, unit tests, build. 3. Fail fast; show the failing test clearly. 4. Cache dependencies. 5. Pin action versions. 6. Never print secrets; use the CI secret store. 7. A red build blocks merging; fix or revert quickly.

## ops.release
title: Release a version
roles: pm, qa, cto, employee
stages: release
keywords: release, version, deploy, launch, changelog, rollout, rollback, notes
source: AGO original (Claude, 2026-11-24)
---
1. Freeze scope; all tests and QA passed with evidence. 2. Version number (semver) and changelog in plain words. 3. Backup data before migrations. 4. Release to a small group first if possible. 5. Watch errors and key metrics for the first hours. 6. Have a tested rollback plan. 7. Announce what changed and how to get help.

## ops.monitoring
title: Monitoring and alerts
roles: employee, cto
stages: release
keywords: monitoring, logs, alerts, uptime, metrics, observability, incident
source: AGO original (Claude, 2026-11-24)
---
1. Log structured events with request ids; never log secrets or personal data. 2. Track the four signals: traffic, errors, latency, saturation. 3. Uptime check from outside. 4. Alert only on things a human must act on; route to one owner. 5. Dashboards for the main user journey. 6. Keep logs for a defined period. 7. Review alerts monthly and remove noisy ones.

## ops.incident-response
title: Handle a production incident
roles: employee, cto, pm
stages: release
keywords: incident, outage, down, emergency, postmortem, recovery, failure
source: AGO original (Claude, 2026-11-24)
---
1. Declare the incident and one person in charge. 2. Stop the bleeding first: rollback, disable the feature, scale. 3. Communicate status to users early and regularly. 4. Keep a timeline of actions. 5. Confirm recovery with real checks. 6. Blameless postmortem within days: cause, impact, what we change. 7. Track follow-up fixes to done.

## ops.backup
title: Backups and restore
roles: employee, cto, risk
stages: architecture, release
keywords: backup, restore, recovery, disaster, data, loss, snapshot
source: AGO original (Claude, 2026-11-24)
---
1. Decide how much data you can lose (RPO) and how long you can be down (RTO). 2. Automatic backups on that schedule, stored in a separate place. 3. Encrypt backups. 4. Test a full restore regularly; an untested backup is not a backup. 5. Keep several versions. 6. Document the restore steps. 7. Alert when a backup fails.
