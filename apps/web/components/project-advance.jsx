"use client";
import {useRef,useState} from 'react';
import {CREDITS_PER_CHAIN_RUN} from './task-self-check-state';
import {MAX_LOST_ANSWERS,MAX_PROGRESS_STEPS,MAX_REVISIONS,QA_CREDITS,lostAnswerWaitMs,
 nextAdvanceStep,stepLabel,transientError,waitMs} from './project-advance-state';

const BASE='/v1/organization/company/projects/';
const clock=ms=>new Date(Date.now()+ms).toLocaleTimeString();

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
  return r;
 }

 // Sleeps in 1 s slices so "Stop" takes effect at once. Returns false if stopped.
 async function pause(ms){
  for(let left=ms;left>0;left-=1000){
   if(stop.current)return false;
   await new Promise(done=>setTimeout(done,Math.min(1000,left)));
  }
  return !stop.current;
 }

 async function go(keepGoing){
  if(busy||!allow)return;
  setBusy(true);setError('');stop.current=false;
  let steps=0,lost=0;
  try{
   for(let turn=0;turn<MAX_PROGRESS_STEPS*6;turn++){
    let r;
    try{r=await perform(await detail());lost=0;}
    catch(e){
     // A lost answer is not a refusal: the server may be restarting. Ask
     // again later; the server reads its recorded state and never replays.
     if(!keepGoing||!transientError(e)||++lost>MAX_LOST_ANSWERS)throw e;
     const ms=lostAnswerWaitMs(lost);
     add('AGO did not answer ('+(e.message||'no answer')+'). Asking again at '+clock(ms)+'.','info');
     if(!await pause(ms)){add('Stopped by the Founder.','stop');break;}
     continue;
    }
    await onChanged?.();
    if(r.done||r.needs_founder||!keepGoing)break;
    if(r.progressed){
     if(++steps>=MAX_PROGRESS_STEPS){add('Paused after '+MAX_PROGRESS_STEPS+' steps. Press again to continue.','stop');break;}
     if(stop.current){add('Stopped by the Founder after this step.','stop');break;}
     continue;
    }
    // A wait (calendar, Docker, Ollama, a running task): keep this page open
    // and AGO carries on by itself when it is due.
    const ms=waitMs(r);
    add('Waiting; AGO asks again at '+clock(ms)+'. Keep this page open or press Stop.','info');
    if(!await pause(ms)){add('Stopped by the Founder.','stop');break;}
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
   Failed work and QA feedback go directly to the responsible agent; after six automatic attempts the AI CEO reports to you. With “Keep going”, waits (work calendar, Docker, Ollama, a server restart) do not stop it: keep this page open and AGO carries on when it is due. A run uses {CREDITS_PER_CHAIN_RUN} internal credits and a QA check {QA_CREDITS}.</p>
  {preview?<p role="status">Next step: {stepLabel(preview)}.</p>:
   <button type="button" disabled={busy} onClick={look} aria-label={'Show the next step for '+project.title}>Show next step</button>}
  <label className="project-advance-allow"><input type="checkbox" checked={allow} disabled={busy}
   onChange={e=>setAllow(e.target.checked)}/>Allow AGO to do these steps and use internal AI credits for {project.title}</label>
  <div className="delivery-actions">
   <button type="button" disabled={busy||!allow} onClick={()=>go(false)}>{busy?'Working…':'Do the next step'}</button>
   <button type="button" disabled={busy||!allow} onClick={()=>go(true)}>Keep going until I am needed</button>
   {busy&&<button type="button" onClick={()=>{stop.current=true;}}>Stop</button>}
  </div>
  {error&&<p role="alert">{error}</p>}
  {log.length>0&&<ol className="project-advance-log" tabIndex={0} aria-label={'Steps AGO took for '+project.title} aria-live="polite">
   {log.map((item,i)=><li key={i} className={'tone-'+item.tone}><time>{item.at}</time> {item.text}</li>)}
  </ol>}
 </div>;
}
