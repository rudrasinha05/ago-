// "Advance project": decide the ONE next step for a Founder-approved project
// from the signed project detail. The server stays the authority for every
// step (approval, hierarchy, self-check, credits, run, QA); this only chooses
// which existing endpoint to call next, and stops whenever a person must act.
import {CREDITS_PER_CHAIN_RUN} from './task-self-check-state.js';

export const QA_CREDITS=1;
const KINDS={
 request:'Ask for approval of the {stage} task',
 approve:'Get AI team approval for the {stage} task (manager → project manager → CEO)',
 run:'Run the {stage} task with the AI team (uses '+CREDITS_PER_CHAIN_RUN+' internal credits)',
 qa:'AI QA checks the {stage} stage (uses '+QA_CREDITS+' internal credit)',
 running:'The {stage} task is running — wait for it to finish',
 rework:'AI QA failed the {stage} stage — the AI project manager creates a rework task',
 open_stage:'The AI project manager opens the {stage} stage and assigns its task',
 failed:'The {stage} task failed — Founder: recover the stage',
 revise:'Revise the {stage} proposal to fix the Board feedback and resubmit it',
 retry_code:'Retry the {stage} task: the AI developer\'s code failed AGO\'s code check',
 revise_limit:'The Board denied the {stage} proposal again after 2 revisions — Founder: read the Board feedback and decide',
 rejected:'The {stage} task approval was rejected — Founder decides what to do',
 unstaffed:'The {stage} stage has no AI worker — staff it first',
 unknown:'The {stage} stage is in a state AGO cannot advance automatically',
 done:'Every stage passed AI QA',
};
// Steps AGO can do by itself; every other kind needs a person and stops a loop.
// The server decides open_stage and rework in the name of the project's AI manager
// (POST …/continue) and says when the Founder is needed instead.
export const AUTOMATIC=new Set(['request','approve','run','qa','revise','retry_code','rework','open_stage']);
export const MANAGER_DECISIONS=new Set(['rework','open_stage']);
export const MAX_REVISIONS=2;

export function stepLabel(step){
 return KINDS[step.kind].replace('{stage}',step.stage||'');
}

/** First stage (by position) that has not passed QA decides the next step. */
export function nextAdvanceStep(detail){
 const stages=(Array.isArray(detail?.stages)?detail.stages:[]).slice()
  .sort((a,b)=>Number(a.position)-Number(b.position));
 if(!stages.length)return {kind:'unstaffed',stage:'first'};
 for(const s of stages){
  if(s.qa_verdict==='pass')continue;
  const base={stage:s.stage,task_id:s.task_id||null};
  // Every earlier stage passed QA here. A later stage with an approved specialist
  // but no task yet is opened by the AI project manager on the server.
  if(!s.task_id)return {...base,kind:Number(s.position)>1&&s.approved_assignee_id?'open_stage':'unstaffed'};
  if(s.qa_verdict==='fail')return {...base,kind:'rework'};
  switch(s.task_status){
   case 'failed':
    // A Board stop (the AI run itself completed) is revised and resubmitted;
    // a crash, timeout or credit failure needs the Founder.
    if(s.agent_failure_code==='engineering_candidate_invalid')return {...base,kind:'retry_code'};
    return {...base,kind:s.agent_run_status==='completed'&&!s.agent_failure_code?'revise':'failed'};
   case 'proposed':return {...base,kind:'request'};
   case 'waiting_approval':
    if(s.task_approval_status==='approved')return {...base,kind:'run'};
    if(s.task_approval_status==='rejected')return {...base,kind:'rejected'};
    return {...base,kind:'approve'};
   case 'running':return {...base,kind:'running'};
   case 'completed':
    return s.agent_run_status==='completed'?{...base,kind:'qa'}:{...base,kind:'unknown'};
   default:return {...base,kind:'unknown'};
  }
 }
 return {kind:'done',stage:''};
}

/** AI QA reviewer: a QA-role AI employee who is not this stage's worker (server re-checks). */
export function pickQaReviewer(reviewers,stage){
 const builders=new Set([stage?.approved_assignee_id,stage?.suggested_assignee_id].filter(Boolean));
 return (Array.isArray(reviewers)?reviewers:[]).find(e=>!builders.has(e.id))||null;
}

const BOARD_REASONS={
 unverified:'its AI answer had no single clear "BOARD_RECOMMENDATION: APPROVE" or "DENY" line, so AGO could not verify a vote',
 deny:'it recommended DENY',
};
/** Why a recorded run did NOT deliver, in plain words; null when it completed and delivered. */
export function runBlocker(result){
 if(!result||typeof result!=='object')return 'The run returned no recorded result. Inspect the stage before anything else.';
 const r=result.result&&typeof result.result==='object'?result.result:{};
 if(r.board_blocked===true){
  const seat=typeof r.blocked_by_board_seat==='string'?r.blocked_by_board_seat:'A Board seat';
  const why=BOARD_REASONS[r.board_block_reason]||'it did not clear the work';
  const done=Number.isFinite(r.roles_completed)&&Number.isFinite(r.roles_expected)?' ('+r.roles_completed+' of '+r.roles_expected+' AI roles ran)':'';
  const reason=(Array.isArray(r.board_recommendations)?r.board_recommendations:[]).find(v=>v&&v.seat===seat)?.denial_reason;
  const said=typeof reason==='string'&&reason?' Reason given: “'+reason+'”.':'';
  return 'The Board stopped the AI team: '+seat+' — '+why+done+'.'+said+(r.founder_override_available===true
   ?' The AI CEO and CTO approved, so you can allow the project on the stage card.'
   :' The stage is marked failed; recover it to try again.');
 }
 if(result.status!=='completed')return 'The run ended as '+(result.status||'unknown')+'. Inspect the stage before anything else.';
 if(result.delivery_status&&result.delivery_status!=='completed'&&result.delivery_status!=='delivered')
  return 'The run finished but delivery is '+result.delivery_status+'. Inspect the stage before anything else.';
 return null;
}

/** Recovery reason that carries the Board feedback into the next attempt. */
export function revisionReason(votes){
 const points=(Array.isArray(votes)?votes:[]).filter(v=>v&&v.recommendation!=='approve')
  .map(v=>v.seat+': '+(v.reason||(v.recommendation==='unverified'?'gave no clear vote':'denied without a stated reason')));
 return ('Revise to fix Board feedback: '+(points.join('; ')||'Board did not approve')).slice(0,500);
}
