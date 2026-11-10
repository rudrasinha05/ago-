"use client";
import {useRef,useState} from 'react';
import {CREDITS_PER_CHAIN_RUN} from './task-self-check-state';
import {MAX_REVISIONS,QA_CREDITS,nextAdvanceStep,stepLabel} from './project-advance-state';

const BASE='/v1/organization/company/projects/';
const MAX_STEPS=12;

/** Founder: let AGO do the next governed step(s) of a project and show each one live. */
export function ProjectAdvance({api,project,onChanged}){
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

 // The server owns every mutation and rechecks fresh state before acting.
 async function perform(current){
  setPreview(nextAdvanceStep(current));
  const r=await api.request('/v1/agents/projects/'+id+'/advance',{method:'POST',timeoutMs:270000});
  if(r?.kind!=='ago_project_advance_v1'||typeof r.progressed!=='boolean'||typeof r.needs_founder!=='boolean')
   throw new Error('The next step could not be verified');
  add(r.message||'Project status updated.',r.needs_founder?'stop':r.progressed||r.done?'ok':'info');
  const followup=r.followup||r.decision?.followup;
  if(followup){
   add('Assigned to '+followup.owner_name+': '+followup.feedback+' Next: '+followup.next_action);
  }
  if(r.scheduled||r.schedule_at){
   add('The schedule is saved. A running authorized project session can resume it when due; otherwise resume this project later.','info');
   return false;
  }
  return r.progressed&&!r.needs_founder&&!r.done;
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
   If the Board denies, AGO sends the Board’s reasons back to the team and resubmits a revised proposal (up to {MAX_REVISIONS} times).
   Failed work and QA feedback go directly to the responsible agent. Calendar waits are saved; repeated failures or authority limits need a decision. This browser session stops when it needs to wait. A run uses {CREDITS_PER_CHAIN_RUN} internal credits and a QA check {QA_CREDITS}.</p>
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
