// Read-only projection of the signed overview. Never infer release or write authority.
export const DELIVERY_STATES={
 blocked:['Blocked — review required','Review the failed stage or rejected plan before taking another action.'],
 waiting_for_independent_qa:['Independent QA required','Execution is recorded; a separate authorized reviewer must assess the work.'],
 working:['Work in progress','Follow the recorded running tasks.'],
 awaiting_project_plan_approval:['Plan review required','Inspect the scope and submit or review the plan.'],
 internally_reviewed:['Stages reviewed','Stage QA has passed. Verify Docker and GitHub delivery evidence separately.'],
 awaiting_governed_execution:['Execution pending','Review assignments and task approvals before running work.'],
};
const object=x=>x!==null&&typeof x==='object'&&!Array.isArray(x);
const optionalText=x=>x==null||typeof x==='string';
const identifier=x=>typeof x==='string'&&x.length>0&&x.length<=100;
// `approval:founder` is not a stored grant: the server evaluates it from the
// signed identity (active human Founder) and /v1/console/me never lists it.
// Requiring it here hid the journey from every real Founder. The server still
// enforces it on the overview request; a 403 is shown as an error.
export const DELIVERY_READ_PERMISSIONS=['organization:read','brain:read','approval:read'];
export function canReadDelivery(me){
 return Boolean(me?.roles?.includes('founder')&&DELIVERY_READ_PERMISSIONS.every(p=>me.permissions?.includes(p)));
}
export function deliveryPage(value){
 if(!object(value)||value.kind!=='ago_founder_delivery_overview_v1'||value.read_only!==true||
    !Array.isArray(value.projects)||value.projects.length>20||typeof value.more_projects_possible!=='boolean')throw new Error('Complete project delivery evidence is unavailable.');
 const seen=new Set();
 for(const p of value.projects){
  if(!object(p)||!identifier(p.project_id)||seen.has(p.project_id)||typeof p.title!=='string'||!p.title.trim()||
    !Object.hasOwn(DELIVERY_STATES,p.delivery_state)||!Array.isArray(p.stages)||p.stages.length>20||
    !optionalText(p.manager)||!optionalText(p.plan_status)||
    !Array.isArray(p.pending_approvals)||p.pending_approvals.length>100||p.pending_approvals.some(a=>!object(a)||!identifier(a.approval_id))||
    p.stages.some(s=>!object(s)||typeof s.stage!=='string'||
      ![s.employee,s.task_status,s.agent_failure_code].every(optionalText)||
      ![null,'pass','fail'].includes(s.qa_verdict)||
      (s.task_id!=null&&!identifier(s.task_id))))throw new Error('Incomplete project delivery record.');
  seen.add(p.project_id);
 }
 return value;
}
export function projectTaskIds(project){
 return [...new Set(project.stages.map(s=>s.task_id).filter(identifier))];
}
export function reviewedStages(project){
 return project.stages.filter(s=>s.task_status==='completed'&&s.qa_verdict==='pass').length;
}
const DECISION_LABELS={plan_review:'Approve the project plan',task_execution:'Consent to run an AI task',governance_action:'Governed decision',opportunity_review:'Business opportunity review',market_signal_review:'Market signal review'};
// Only requests the server marks as needing the Founder; others go to independent reviewers.
export function founderDecisions(project){
 return (project.pending_approvals||[]).filter(a=>a.requires_founder_decision===true).map(a=>({
  approval_id:a.approval_id,label:typeof a.type==='string'&&a.type?DECISION_LABELS[a.type]||a.type.replaceAll('_',' '):'Decision'}));
}
// Evidence is verified only when the signed overview says exactly true.
export function deliveryEvidence(project){
 return [['docker','Docker QA',project.docker_qa_verified],['commit','GitHub commit',project.github_commit_verified],
  ['pr','Draft PR',project.draft_pr_verified],['release','Release ready',project.release_ready]]
  .map(([key,label,value])=>({key,label,verified:value===true}));
}
