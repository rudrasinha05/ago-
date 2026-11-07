// Read-only projection of the signed overview. Never infer release or write authority.
export const DELIVERY_STATES={
 blocked:['Blocked — review required','Review the failed stage or rejected plan before taking another action.'],
 waiting_for_independent_qa:['Independent QA required','Execution is recorded. Ask an AI QA employee who did not build it to check each finished stage.'],
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
// Task approval state per task (Issue #7, found on the Founder's live AGO).
// A governed task keeps status `waiting_approval` after its approval is granted
// and only becomes `running` when someone explicitly runs it, so the overview's
// task_status alone made approved work look undecided. Prefer a server field
// `task_approval_status` on the stage when present; otherwise use the newest
// matching row from the approval inbox. Nothing found => keep the raw status.
export function taskApprovalStates(rows){
 const latest=new Map();
 for(const row of Array.isArray(rows)?rows:[]){
  if(!row||!identifier(row.task_id)||typeof row.status!=='string')continue;
  const old=latest.get(row.task_id);
  if(!old||String(row.created_at||'')>String(old.created_at||''))latest.set(row.task_id,row);
 }
 return new Map([...latest].map(([id,row])=>[id,row.status]));
}
const TASK_STATUS={proposed:'Proposed',waiting_approval:'Waiting for approval',running:'Running',completed:'Completed',failed:'Failed',blocked:'Blocked'};
export function stageTaskLabel(stage,approvalStates){
 if(!stage?.task_status)return 'not created';
 if(stage.task_status==='waiting_approval'){
  const decided=['pending','approved','rejected'].includes(stage.task_approval_status)
   ?stage.task_approval_status:approvalStates?.get?.(stage.task_id);
  if(decided==='approved')return 'Approved — ready to run (needs an explicit Run)';
  if(decided==='rejected')return 'Approval rejected — not allowed to run';
 }
 return TASK_STATUS[stage.task_status]||String(stage.task_status).replaceAll('_',' ');
}
// Safe failure codes recorded by the server (issue #10); never exception text.
const FAILURE_REASONS={
 credit_budget_missing:'No internal AI credit allowance was set, so no model call was attempted.',
 credit_budget_exceeded:'The internal AI credit allowance ran out during the run.',
 credit_budget_unavailable:'The internal AI credit allowance refused the run.',
 model_timeout:'The local AI model did not answer in time.',
 model_unreachable:'AGO could not reach the local AI model (Ollama).',
 model_incomplete:'The local AI model returned an incomplete answer.',
 worker_timeout:'The AI worker did not finish in time.',
 handler_error:'The AI run stopped with an unclassified error (older runs record only this).',
};
export function failureReason(code){
 if(typeof code!=='string'||!code)return null;
 return FAILURE_REASONS[code]||'Recorded failure code: '+code;
}
const RECOVERY_STAGES=new Set(['discovery','architecture','implementation','quality','release']);
/** A stage the Founder may recover: linked task failed (server re-checks everything). */
export function recoverableStage(stage){
 return Boolean(stage&&RECOVERY_STAGES.has(stage.stage)&&identifier(stage.task_id)&&
  (stage.task_status==='failed'||qaReworkStage(stage)));
}
/** A finished stage whose independent QA said FAIL: it needs new work (server re-checks). */
export function qaReworkStage(stage){
 return Boolean(stage&&stage.task_status==='completed'&&stage.qa_verdict==='fail');
}
// Issue #8 M4: the Founder is the only human, so a finished stage is checked
// by an independent AI QA employee. Same regex as the server (QA/quality/test).
const QA_ROLE=/\b(qa|quality|test(er|ing)?)\b/i;
/** A finished stage with a completed AI run and no QA verdict yet (server re-checks). */
export function aiQaReadyStage(stage){
 return Boolean(stage&&RECOVERY_STAGES.has(stage.stage)&&stage.task_status==='completed'&&
  stage.agent_run_status==='completed'&&!stage.qa_verdict&&identifier(stage.task_id));
}
/** Active AI employees whose role is QA; the server also excludes the builders. */
export function aiQaReviewers(profiles){
 return (Array.isArray(profiles)?profiles:[]).filter(e=>e&&identifier(e.id)&&e.kind==='ai'&&
  e.status!=='terminated'&&QA_ROLE.test(e.role_title||''));
}
/** Plain reason for a failed stage. A failed task whose AI run itself completed was
 * stopped by the AI Board (no single clear vote, or a DENY) - not a crash. */
export function stageFailureReason(stage){
 if(!stage||stage.task_status!=='failed')return stage?.agent_failure_code?failureReason(stage.agent_failure_code):null;
 if(stage.agent_failure_code)return failureReason(stage.agent_failure_code);
 if(stage.agent_run_status==='completed')return 'The AI Board stopped the work: a Board member gave no single clear APPROVE/DENY line, or said DENY. Recover the stage to try again.';
 return null;
}
const OVERRIDABLE=new Set(['Finance & Budget','Risk & Compliance','Quality & Release']);
/** The recorded Board votes of a blocked AI run (Founder-only result), or null. */
export function boardDenial(result){
 if(!result||result.kind!=='local_company_governed_handoff'||result.board_blocked!==true)return null;
 const votes=(Array.isArray(result.board_recommendations)?result.board_recommendations:[])
  .filter(v=>v&&typeof v.seat==='string'&&typeof v.recommendation==='string')
  .map(v=>({seat:v.seat,recommendation:v.recommendation,reason:typeof v.denial_reason==='string'?v.denial_reason:'',override:v.founder_override===true}));
 const stoppedBy=typeof result.blocked_by_board_seat==='string'?result.blocked_by_board_seat:null;
 if(!stoppedBy)return null;
 const approved=new Set(votes.filter(v=>v.recommendation==='approve').map(v=>v.seat));
 const overridable=OVERRIDABLE.has(stoppedBy)&&approved.has('Strategy & Vision')&&approved.has('Technology Oversight');
 return {votes,stoppedBy,overridable};
}
