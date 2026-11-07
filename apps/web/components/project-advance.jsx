"use client";
import {useRef,useState} from 'react';
import {aiQaReviewers} from './founder-delivery-state';
import {creditBalance,creditBlocker,selfCheck,CREDITS_PER_CHAIN_RUN} from './task-self-check-state';
import {AUTOMATIC,QA_CREDITS,nextAdvanceStep,pickQaReviewer,stepLabel} from './project-advance-state';

const BASE='/v1/organization/company/projects/';
const MAX_STEPS=12;

/** Founder: let AGO do the next governed step(s) of a project and show each one live. */
export function ProjectAdvance({api,project,profiles,onChanged}){
 const [log,setLog]=useState([]),[busy,setBusy]=useState(false),[allow,setAllow]=useState(false);
 const [preview,setPreview]=useState(null),[error,setError]=useState('');
 const stop=useRef(false);
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
  const stage=current.stages.find(s=>s.task_id===step.task_id);
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
   if(r?.status!=='completed'){add('The run ended as '+(r?.status||'unknown')+'. Inspect the stage before anything else.','stop');return false;}
   add('The AI team finished the '+step.stage+' task. The result is recorded.','ok');return true;
  }
  // qa
  const reviewer=pickQaReviewer(aiQaReviewers(profiles),stage);
  if(!reviewer){add('No AI employee with a QA role who did not build this work. Hire or retitle one as “QA Engineer”.','stop');return false;}
  const r=await api.request(BASE+id+'/stages/'+encodeURIComponent(step.stage)+'/ai-qa',
   {method:'POST',body:{qa_employee_id:reviewer.id,operation_key:crypto.randomUUID()}});
  if(r?.verdict==='pass'){add('AI QA by '+r.qa_employee_name+': PASS for '+step.stage+'.','ok');return true;}
  if(r?.verdict==='fail'){add('AI QA by '+r.qa_employee_name+': FAIL for '+step.stage+'. Create a rework task.','stop');return false;}
  add('AI QA gave no clear verdict for '+step.stage+'. Nothing was recorded as QA; try again.','stop');return false;
 }

 async function go(keepGoing){
  if(busy||!allow)return;
  setBusy(true);setError('');stop.current=false;
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
