# Quality assurance skills

## qa.test-plan
title: Write a test plan
roles: qa, quality, pm, employee
stages: quality, implementation
keywords: test, plan, qa, quality, coverage, cases, acceptance, testing
source: AGO original (Claude, 2026-11-24)
---
1. Scope: features in and out of test. 2. Acceptance criteria from the requirement, each testable. 3. Cases: normal, edge, invalid, permission, failure of dependencies. 4. Test levels: unit, integration, end-to-end, accessibility. 5. Data and environment needed. 6. Pass/fail rule and who signs off. 7. Map each case to the requirement it proves.

## qa.review-deliverable
title: QA review of a delivered stage
roles: qa, quality
stages: discovery, architecture, implementation, quality, release
keywords: qa, review, verdict, pass, fail, deliverable, evidence, acceptance, check
source: AGO original (Claude, 2026-11-24)
---
1. Read the stage's acceptance text first. 2. Check each item against the actual deliverable, one by one; quote the evidence. 3. Executed test results beat claims; missing evidence means not proven. 4. List concrete defects with where and how to fix. 5. PASS only if every required item is met; otherwise FAIL with the exact gaps. 6. Never pass work because it "looks fine". 7. End with exactly one verdict line.

## qa.bug-report
title: Write a bug report
roles: qa, employee
stages: quality
keywords: bug, report, defect, issue, reproduce, steps, expected, actual
source: AGO original (Claude, 2026-11-24)
---
1. Title: what is wrong, where. 2. Steps to reproduce, numbered, from a clean start. 3. Expected result vs actual result. 4. Environment: version, browser/OS, data used. 5. Evidence: error text, screenshot, logs (no secrets). 6. Severity and how many users are affected. 7. One bug per report.

## qa.accessibility
title: Accessibility check (WCAG)
roles: qa, employee
stages: implementation, quality
keywords: accessibility, a11y, wcag, screen, reader, contrast, keyboard, aria
source: AGO original (Claude, 2026-11-24)
---
1. Everything works with the keyboard alone; visible focus. 2. Every image has alt text; icons have labels. 3. Text contrast at least 4.5:1. 4. Headings in order; landmarks (main, nav). 5. Form fields have labels and clear errors. 6. No information by color alone. 7. Test with an automated checker (axe) and one screen reader pass.

## qa.regression
title: Regression testing
roles: qa, employee
stages: quality, release
keywords: regression, retest, suite, automated, smoke, release, broken
source: AGO original (Claude, 2026-11-24)
---
1. Keep an automated suite for core journeys. 2. Every fixed bug gets a test. 3. Run the full suite before each release. 4. Smoke test the live system right after release. 5. Flaky tests are bugs: fix or quarantine with an owner. 6. Track time to run; keep it fast. 7. Report results with the exact version tested.

## qa.usability-test
title: Usability test with real users
roles: qa, pm, employee
stages: discovery, quality
keywords: usability, user, test, testing, interview, feedback, ux, prototype
source: AGO original (Claude, 2026-11-24)
---
1. Recruit 5 users who match the target. 2. Give real tasks, not instructions ("Book a session"). 3. Ask them to think aloud; do not help. 4. Note where they hesitate, err or give up. 5. Measure task success and time. 6. Rank problems by frequency and severity. 7. Fix the top issues and test again.
