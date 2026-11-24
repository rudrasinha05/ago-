"use client";
import {useCallback,useEffect,useState} from 'react';
import {decisionsView,managerPool,settingsView,usageLine} from './ai-models-state';

const BASE='/v1/organization/company';

/** The Employee Manager is a part of the Company Brain, not an AI employee:
 * it has no seat, no tasks and no credits of its own. It decides which model
 * does each piece of work (MGR-002) and records why. The Founder sets only the
 * paid-model rule; the Founder Assistant is outside its reach. */
export function BrainManager({api,me,active=true}){
 const founder=Boolean(me?.roles?.includes('founder'));
 const [view,setView]=useState(null),[policy,setPolicy]=useState(null),[decisions,setDecisions]=useState([]);
 const [error,setError]=useState(''),[notice,setNotice]=useState(''),[busy,setBusy]=useState(false);
 const apply=useCallback(raw=>{
  const next=settingsView(raw);
  if(!next)throw new Error('The Employee Manager settings could not be read. Press Refresh.');
  setView(next);setPolicy({allow_paid:next.allow_paid,monthly_call_cap:next.monthly_call_cap});
 },[]);
 const load=useCallback(()=>{
  setError('');
  return Promise.all([
   api.request(BASE+'/cloud-models').then(apply),
   api.request(BASE+'/model-decisions').then(v=>setDecisions(decisionsView(v))),
  ]).catch(e=>setError(e?.message||'The Employee Manager is unavailable.'));
 },[api,apply]);
 useEffect(()=>{if(founder&&active)load();},[founder,active,load]);
 if(!founder)return null;
 async function save(){
  setBusy(true);setError('');setNotice('');
  try{
   apply(await api.request(BASE+'/cloud-model-policy',{method:'PUT',body:{allow_paid:Boolean(policy.allow_paid),
    monthly_call_cap:Math.max(0,Math.min(5000,Number(policy.monthly_call_cap)||0))}}));
   setNotice('Saved. The Employee Manager follows this from the next AI task.');
  }catch(e){setError(e?.message||'That did not work.');}
  finally{setBusy(false);}
 }
 const editable=Boolean(view?.available)&&!busy;
 return <section className="ai-models brain-manager" aria-labelledby="brain-manager-title">
  <header className="ai-models-head">
   <div><h2 id="brain-manager-title">Employee Manager</h2>
    <p>Part of the Company Brain, not an employee. It decides which AI model does each piece of work and writes down why. Your Founder Assistant is outside its control.</p></div>
   <button type="button" onClick={load} disabled={busy}>Refresh</button>
  </header>
  {error&&<p role="alert" className="ai-models-error">{error}</p>}
  {notice&&<p role="status" className="ai-models-notice">{notice}</p>}
  {view&&<>
   <ul className="brain-manager-rules" aria-label="How the Employee Manager decides">
    <li><b>Code and skills</b> need a capable model. A small local model never writes code when a better one is connected.</li>
    <li><b>Free first.</b> Paid models only when no free model is strong enough, a free model's work keeps failing QA, or the stage already failed QA.</li>
    <li><b>QA</b> uses a capable model from a different provider than the builder when it can.</li>
    <li><b>Plans, Board votes and chat</b> stay on free models.</li>
   </ul>
   <p className="ai-manager-pool" aria-label="Models the Employee Manager can use"><b>Can use now:</b> {managerPool(view)}</p>
   <p className="ai-models-hint">{usageLine(view)}. Connect or change models in the AI Models tab.</p>
   <div className="ai-routes">
    <label className="ai-route"><span><b>Allow paid models</b><small>Claude and OpenAI cost money. Off means only free models are used.</small></span>
     <input type="checkbox" checked={Boolean(policy?.allow_paid)} disabled={!editable} onChange={e=>setPolicy(old=>({...old,allow_paid:e.target.checked}))}/></label>
    <label className="ai-route"><span><b>Monthly paid-call limit</b><small>Most paid calls per month. Free models are not counted.</small></span>
     <input type="number" min="0" max="5000" inputMode="numeric" value={policy?.monthly_call_cap??0} disabled={!editable}
      onChange={e=>setPolicy(old=>({...old,monthly_call_cap:e.target.value}))}/></label>
   </div>
   <button type="button" className="ai-primary" disabled={!editable} onClick={save}>{busy?'Saving…':'Save'}</button>
   <h3>Recent decisions</h3>
   {decisions.length?<ul className="ai-decisions" aria-label="Recent model choices">{decisions.slice(0,12).map(d=><li key={d.id}>
     <b>{d.work}</b>{d.role?' · '+d.role:''} → <span className={d.paid?'ai-chip warn':'ai-chip ok'}>{d.model}</span><small>{d.reason}</small></li>)}</ul>
    :<p className="ai-models-hint">No decisions yet. They appear when AI work runs.</p>}
  </>}
 </section>;
}
