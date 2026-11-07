// AGO self-check (self-sufficiency stage 1): translate the server's read-only
// engineering preflight into plain language plus who can fix each blocker.
// The server stays the authority: this never disables or performs a run.
export const PREFLIGHT_KIND='ago_founder_engineering_preflight_v1';

const BLOCKERS={
 task_not_found_for_founder_tenant:['This task was not found in your company.','Refresh the desk.'],
 task_action_not_internal_brief:['This task type cannot be run by the local AI team.','Founder or CTO: create an internal brief task instead.'],
 task_not_awaiting_approved_dispatch:['This task is not waiting to run (it is already running, finished or not requested).','Check the task history before doing anything else.'],
 matching_approval_not_approved:['Its approval has not been granted yet.','The authorized approver decides it in Approvals.'],
 founder_discovery_link_missing:['The task is not linked to an approved Founder project.','Start work from an approved project in Projects.'],
 project_discovery_link_missing:['The task is not linked to an approved Founder project.','Start work from an approved project in Projects.'],
 founder_project_not_active_or_discovery_link_missing:['The project plan is not active, or its discovery task is not linked.','Founder: approve and activate the project plan.'],
 five_board_review_not_configured:['The five-member AI Board review is not switched on.','Start AGO with START_AGO.cmd (engineering mode).'],
 local_environment_not_allowed:['Local AI runs are only allowed on your local development AGO.','Run AGO locally with START_AGO.cmd.'],
 board_appointments_incomplete:['Not all five AI Board seats (CEO, CTO, CFO, CISO, CQO) are appointed.','Founder: appoint them in Board & Roles.'],
 pm_or_discovery_employee_missing:['The project has no accountable manager or no discovery worker.','Founder or CEO: staff the project in Projects.'],
 worker_pm_reporting_path_missing:['The worker does not report to the project manager.','Fix the reporting line in Board & Roles → Review employee reporting links.'],
 board_pm_or_worker_not_ai:['The project manager, a Board seat or the worker is not an AI employee (for example, the Founder is recorded as project manager).','Assign an AI Project Manager to the project (backend request: GitHub issue #9).'],
 board_pm_worker_identities_not_distinct:['One employee holds two roles in the AI chain.','Give each Board seat, the manager and the worker to different employees.'],
 implementation_stage_not_activated:['No AI developer is activated for the implementation stage.','Founder or CEO: activate the implementation stage in Projects.'],
 seven_distinct_ai_employees_required:['The AI chain needs seven different AI employees.','Fill the missing Board, manager or worker roles.'],
 prior_run_found_do_not_replay:['This task already ran once. AGO never replays a run automatically.','Inspect the recorded result; for a failed run, request a new authorized recovery task.'],
 company_hierarchy_not_verified:['The company hierarchy could not be verified for this task.','Review Board & Roles and the project staffing.'],
};
const GATES={
 calendar_at_dispatch_time:'work calendar',constitutional_permission_at_dispatch:'company rules',
 task_execute_grant:'run permission',employee_behavior_review:'employee conduct review',
 virtual_credit_budget:'budget',local_ollama_response:'local Ollama model',
};
const known=code=>Object.prototype.hasOwnProperty.call(BLOCKERS,code);

export function selfCheck(report){
 if(!report||report.kind!==PREFLIGHT_KIND||!Array.isArray(report.blocking_checks))
  throw new Error('Unexpected self-check response.');
 const blockers=[...new Set(report.blocking_checks.filter(c=>typeof c==='string'))].map(code=>{
  const [what,fix]=known(code)?BLOCKERS[code]:['Blocked by a check this screen does not know yet ('+code+').','Ask the Founder or CTO to review it.'];
  return {code,what,fix};
 });
 const evidence=report.reporting_repair_evidence;
 const repair=evidence&&typeof evidence.worker_name==='string'&&typeof evidence.accountable_pm_name==='string'
  ?evidence.worker_name+' reports to '+(evidence.worker_manager_name||'nobody')+'; it must report to project manager '+evidence.accountable_pm_name+'.'
  :null;
 const laterGates=(Array.isArray(report.unverified_execution_gates)?report.unverified_execution_gates:[])
  .map(g=>GATES[g]||String(g).replaceAll('_',' '));
 return {ready:blockers.length===0,blockers,repair,laterGates,
  roles:Array.isArray(report.assigned_role_names)?report.assigned_role_names.filter(r=>typeof r==='string'):[]};
}

// The server checks credits only at Run; the allowance is readable before.
// `credits` is the recorded balance (null/undefined = unknown: add nothing).
// Internal AI credits cap how many local model calls AGO may attempt; they are
// not money. One full AI-team run (5 Board roles, PM, worker) uses 7 credits.
export const CREDITS_PER_CHAIN_RUN=7;
const finite=value=>{const n=Number(value);return Number.isFinite(n)?n:null;};
/** Parse the scorecard's virtual_credit_budget; null when not readable. */
export function creditBalance(scorecard){
 const b=scorecard?.virtual_credit_budget;
 if(!b)return null;
 const ceiling=finite(b.ceiling),consumed=finite(b.consumed),remaining=finite(b.remaining);
 if(ceiling===null||consumed===null||remaining===null||ceiling<0||consumed<0)return null;
 return {ceiling,consumed,remaining};
}
export function creditBlocker(check,credits){
 if(!check||!credits||typeof credits.remaining!=='number'||credits.remaining>=CREDITS_PER_CHAIN_RUN)return check;
 const what='Not enough internal AI credits: '+credits.remaining+' left, and one AI-team run needs '+CREDITS_PER_CHAIN_RUN+'.';
 return {...check,ready:false,blockers:[...check.blockers,{code:'virtual_credit_budget_low',what,
  fix:'Founder: raise the AI credit allowance on this desk (internal credits, not money).'}]};
}
