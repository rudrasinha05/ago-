"use client";
import {useRef,useState} from 'react';
import {aiQaReviewers} from './founder-delivery-state';
import {creditBalance,creditBlocker,selfCheck,CREDITS_PER_CHAIN_RUN} from './task-self-check-state';
import {AUTOMATIC,MANAGER_DECISIONS,MAX_REVISIONS,QA_CREDITS,nextAdvanceStep,pickQaReviewer,revisionReason,runBlocker,stepLabel} from './project-advance-state';
import {boardDenial} from './founder-delivery-state';

const BASE='/v1/organization/company/projects/';
const MAX_STEPS=12;

/** Founder: let AGO do the next governed step(s) of a project and show each one live. */
export function ProjectAdvance({api,project,profiles,onChanged}){
 const [log,setLog]=useState([]),[busy,setBusy]=useState(false),[allow,setAllow]=useState(false);
 const [preview,setPreview]=useState(null),[error,setError]=useState('');
 const stop=useRef(false),revisions=useRef(0);
 const id=encodeURIComponent(project.project_id);
 const add=(text,tone='info')=>setLog(items=>[...items,{at:new Date().toLocaleTimeString(),text,tone}]);

 async function detail(){return api.request(BASE+id);}
 async function look(){
  setError('');
  try{setPreview(nextAdvanceStep(await detail()));}
  catch(e){setError(e.message||'Project details unavailable.');}
 }

 // Performs exactly one step; returns true when a loop may continue.
 async function perform(current){
  const step=nextAdvanceStep(current);
  setPreview(step);
  if(!AUTOMATIC.has(step.kind)){add(stepLabel(step)+'. AGO stopped here.',step.kind==='done'?'ok':'stop');return false;}
  add('Next: '+stepLabel(step)+'…');
  if(MANAGER_DECISIONS.has(step.kind)){
   // PROJ-006: the server decides this in the name of the project's AI manager and records it.
   return managerDecision(await api.request(BASE+id+'/continue',{method:'POST'}));
  }
  const stage=current.stages.find(s=>s.task_id===step.task_id);
  if(step.kind==='revise'||step.kind==='retry_code'){
   if(revisions.current>=MAX_REVISIONS){add(stepLabel({...step,kind:'revise_limit'})+'. AGO stopped here.','stop');return false;}
   const view=boardDenial(stage?.founder_agent_result);
   const reason=step.kind==='retry_code'?'Retry after the AI developer\'s code failed AGO\'s code check (Board had approved)':revisionReason(view?.votes);
   const r=await api.request(BASE+id+'/stages/'+encodeURIComponent(step.stage)+'/recovery',
    {method:'POST',body:{failed_task_id:step.task_id,reason}});
   if(r?.kind!=='ago_stage_task_recovery_v1'||r.run_started!==false){add('The revision was not recorded. Check the stage before retrying.','stop');return false;}
   revisions.current++;
   add(step.kind==='retry_code'?'New task created to retry the code (attempt '+revisions.current+' of '+MAX_REVISIONS+').'
    :'Board feedback sent to the team for revision '+revisions.current+' of '+MAX_REVISIONS+': '+reason.replace(/^Revise to fix Board feedback: /,'')+'. The revised proposal will go back to the Board.','ok');
   return true;
  }
  if(step.kind==='request'){
   const r=await api.request('/v1/console/tasks/'+encodeURIComponent(step.task_id)+'/request-approval',{method:'POST'});
   add('Approval requested for '+step.stage+' ('+(r?.status||'recorded')+').','ok');return true;
  }
  if(step.kind==='approve'){
   const r=await api.request(BASE+id+'/ceo/reconcile',{method:'POST'});
   const who=(r?.task_approvers||[]).find(a=>a.task_id===step.task_id);
   if(!who){add('The AI team could not approve the '+step.stage+' task. The Founder decides it in Approvals.','stop');return false;}
   add(who.approver_name+' ('+who.approver_level.replace('_',' ')+') approved the '+step.stage+' task and is responsible for it.','ok');return true;
  }
  if(step.kind==='run'){
   const check=selfCheck(await api.request('/v1/agents/tasks/'+encodeURIComponent(step.task_id)+'/engineering-preflight'));
   const credits=creditBalance(await api.request('/v1/insights/scorecard').catch(()=>null));
   const view=creditBlocker(check,credits);
   if(!view.ready){add('Self-check blocked the run: '+view.blockers.map(b=>b.what+' ('+b.fix+')').join(' '),'stop');return false;}
   add('Self-check passed. The AI team is working on '+step.stage+' (this can take a few minutes)…');
   const r=await api.request('/v1/agents/tasks/'+encodeURIComponent(step.task_id)+'/run',{method:'POST',timeoutMs:270000});
   const revised=r?.result?.revised_scope;
   if(revised&&typeof revised.draft==='string')add(revised.employee_name+' (project manager) rewrote the scope to fix the Board feedback: '+
    revised.draft.replace(/\s+/g,' ').slice(0,240)+(revised.draft.length>240?'…':''),'ok');
   const blocked=runBlocker(r);
   if(blocked){
    // A Board stop is not the end: the next step revises and resubmits (bounded).
    const board=r?.result?.board_blocked===true;
    add(blocked.replace(/ The stage is marked failed; recover it to try again\.$/,'')+(board?' AGO will revise the proposal and resubmit it.':''),board?'info':'stop');
    return board;
   }
   add('The AI team finished the '+step.stage+' task. The result is recorded.','ok');return true;
  }
  // qa
  const reviewer=pickQaReviewer(aiQaReviewers(profiles),stage);
  if(!reviewer){add('No AI employee with a QA role who did not build this work. Hire or retitle one as “QA Engineer”.','stop');return false;}
  const r=await api.request(BASE+id+'/stages/'+encodeURIComponent(step.stage)+'/ai-qa',
   {method:'POST',body:{qa_employee_id:reviewer.id,operation_key:crypto.randomUUID()}});
  if(r?.verdict==='pass'){
   add('AI QA by '+r.qa_employee_name+': PASS for '+step.stage+'.','ok');
   // The server's AI manager may already have opened the next stage.
   return r.continuation?managerDecision(r.continuation,true):true;
  }
  if(r?.verdict==='fail'){
   if(r.continuation){add('AI QA by '+r.qa_employee_name+': FAIL for '+step.stage+'.','info');return managerDecision(r.continuation);}
   add('AI QA by '+r.qa_employee_name+': FAIL for '+step.stage+'. Create a rework task.','stop');return false;
  }
  add('AI QA gave no clear verdict for '+step.stage+'. Nothing was recorded as QA; try again.','stop');return false;
 }

 // Shows what the AI project manager decided on the server; true when the loop may go on.
 function managerDecision(r,quietWhenIdle=false){
  const who=(r?.decided_by_name||'The AI project manager')+' (AI project manager)';
  if(r?.action==='opened_stage'){
   add(who+' opened the '+r.stage+' stage and assigned its task to '+(r.assignee_name||'the approved specialist')+'.','ok');return true;
  }
  if(r?.action==='recovered_stage'){
   add(who+' created a new '+r.stage+' task (automatic attempt '+r.ai_recovery_attempt+' of '+r.ai_recovery_limit+'): '+r.reason,'ok');return true;
  }
  if(quietWhenIdle&&r?.needs_founder===false)return true;
  add((r?.reason||'The AI project manager could not decide the next step.')+' AGO stopped here.',r?.state==='all_stages_passed'?'ok':'stop');
  return false;
 }

 async function go(keepGoing){
  if(busy||!allow)return;
  setBusy(true);setError('');stop.current=false;revisions.current=0;
  try{
   for(let i=0;i<(keepGoing?MAX_STEPS:1);i++){
    const more=await perform(await detail());
    await onChanged?.();
    if(!more)break;
    if(stop.current){add('Stopped by the Founder after this step.','stop');break;}
    if(keepGoing&&i===MAX_STEPS-1)add('Paused after '+MAX_STEPS+' steps. Press again to continue.','stop');
   }
   setPreview(nextAdvanceStep(await detail()));
  }catch(e){
   add((e.message||'Step failed')+'. The server may still have recorded it; check the stage before retrying.','stop');
  }finally{setBusy(false);setAllow(false);}
 }

 const label='Advance '+project.title;
 return <div className="project-advance" role="group" aria-label={label}>
  <p><strong>Let AGO move this project forward.</strong> AGO does the next allowed step itself: ask for approval,
   get the AI team’s approval, run the AI team after its self-check, and have an independent AI QA check the result.
   If the Board denies, AGO sends the Board’s reasons back to the team and resubmits a revised proposal (up to {MAX_REVISIONS} times).
   It stops whenever you are needed. A run uses {CREDITS_PER_CHAIN_RUN} internal credits and a QA check {QA_CREDITS}.</p>
  {preview?<p role="status">Next step: {stepLabel(preview)}.</p>:
   <button type="button" disabled={busy} onClick={look} aria-label={'Show the next step for '+project.title}>Show next step</button>}
  <label className="project-advance-allow"><input type="checkbox" checked={allow} disabled={busy}
   onChange={e=>setAllow(e.target.checked)}/>Allow AGO to do these steps and use internal AI credits for {project.title}</label>
  <div className="delivery-actions">
   <button type="button" disabled={busy||!allow} onClick={()=>go(false)}>{busy?'Working…':'Do the next step'}</button>
   <button type="button" disabled={busy||!allow} onClick={()=>go(true)}>Keep going until I am needed</button>
   {busy&&<button type="button" onClick={()=>{stop.current=true;}}>Stop after this step</button>}
  </div>
  {error&&<p role="alert">{error}</p>}
  {log.length>0&&<ol className="project-advance-log" tabIndex={0} aria-label={'Steps AGO took for '+project.title} aria-live="polite">
   {log.map((item,i)=><li key={i} className={'tone-'+item.tone}><time>{item.at}</time> {item.text}</li>)}
  </ol>}
 </div>;
}
