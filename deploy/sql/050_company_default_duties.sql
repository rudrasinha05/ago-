-- Default duties for legacy and newly created employees until founder specifies a role.
-- Defaults describe obligations, never grant permissions or falsely claim a job title.
ALTER TABLE ago_employees ALTER COLUMN core_responsibilities
 SET DEFAULT 'Deliver approved assigned work with evidence, independent QA and clear escalation of blockers.';
ALTER TABLE ago_employees ALTER COLUMN extra_responsibilities
 SET DEFAULT 'Maintain project documentation, verify tests, record progress and support release handover.';
UPDATE ago_employees
 SET core_responsibilities='Deliver approved assigned work with evidence, independent QA and clear escalation of blockers.'
 WHERE core_responsibilities='';
UPDATE ago_employees
 SET extra_responsibilities='Maintain project documentation, verify tests, record progress and support release handover.'
 WHERE extra_responsibilities='';
