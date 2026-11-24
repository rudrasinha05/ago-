"use client";
import {useCallback,useEffect,useState} from 'react';
import {PROVIDER_INFO,connectText,decisionsView,errorText,managerPool,providerStatus,settingsView,usageLine} from './ai-models-state';

const BASE='/v1/organization/company';

/** Founder's AI model settings. The Founder connects models; the Workforce
 * Manager (MGR-002) decides which model does each piece of work and records
 * why. The Founder only sets whether paid models are allowed and their monthly
 * limit. Keys are write-only: after Save the browser never sees them again. */
export function AiModels({api,me,active=true}){
 const founder=Boolean(me?.roles?.includes('founder'));
 const [view,setView]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [drafts,setDrafts]=useState({}),[models,setModels]=useState({}),[busy,setBusy]=useState('');
 const [policy,setPolicy]=useState(null),[workspace,setWorkspace]=useState(''),[decisions,setDecisions]=useState([]);
 const apply=useCallback(raw=>{
  const next=settingsView(raw);
  if(!next)throw new Error('AI model settings could not be read. Press Refresh.');
  setView(next);setPolicy({allow_paid:next.allow_paid,monthly_call_cap:next.monthly_call_cap});
 },[]);
 useEffect(()=>{
  if(!founder||!active)return undefined;
  let live=true;
  api.request(BASE+'/cloud-models').then(v=>{if(live){apply(v);setError('');}})
   .catch(e=>{if(live)setError(e?.message||'AI model settings are unavailable.');});
  api.request(BASE+'/model-decisions').then(v=>{if(live)setDecisions(decisionsView(v));}).catch(()=>{});
  return()=>{live=false;};
 },[api,founder,active,apply]);
 if(!founder)return <div className="ai-models"><h2>AI models</h2><p>Only the Founder can add or change AI models.</p></div>;
 const keyOf=name=>drafts[name]||'';
 const setKey=(name,value)=>setDrafts(old=>({...old,[name]:value}));
 async function act(label,work,done){
  setBusy(label);setError('');setNotice('');
  try{const result=await work();if(result?.providers)apply(result);if(done)done(result);}
  catch(e){setError(e?.message||'That did not work.');}
  finally{setBusy('');}
 }
 // One step: AGO checks the key, picks the code model, tests it and uses it.
 const connect=name=>act(name+':connect',()=>api.request(BASE+'/cloud-models/'+name+'/connect',{method:'POST',body:{api_key:keyOf(name).trim(),...(name==='anthropic'&&workspace.trim()?{workspace_id:workspace.trim()}:{})},timeoutMs:400000}),
  r=>{setKey(name,'');setNotice(connectText(PROVIDER_INFO[name].name,r.connect));});
 const useModel=(name,model)=>act(name+':model',()=>api.request(BASE+'/cloud-models/'+name+'/model',{method:'PUT',body:{model},timeoutMs:65000}),
  r=>{setModels(old=>({...old,[name]:undefined}));setNotice(r.test.ok?PROVIDER_INFO[name].name+' now uses '+model+'.':PROVIDER_INFO[name].name+': '+errorText(r.test.code));});
 const test=name=>act(name+':test',()=>api.request(BASE+'/cloud-models/'+name+'/test',{method:'POST',body:{},timeoutMs:65000}),
  r=>setNotice(r.test.ok?PROVIDER_INFO[name].name+' works.':PROVIDER_INFO[name].name+': '+errorText(r.test.code)));
 const remove=name=>act(name+':remove',()=>api.request(BASE+'/cloud-models/'+name,{method:'DELETE'}),
  ()=>setNotice(PROVIDER_INFO[name].name+' key removed from this computer.'));
 const savePolicy=()=>act('policy',()=>api.request(BASE+'/cloud-model-policy',{method:'PUT',body:{allow_paid:Boolean(policy.allow_paid),monthly_call_cap:Math.max(0,Math.min(5000,Number(policy.monthly_call_cap)||0))}}),
  ()=>setNotice('Saved. The Manager follows this from the next AI task.'));
 const editable=Boolean(view?.available)&&busy==='';
 return <div className="ai-models">
  <header className="ai-models-head">
   <div><h2>AI models</h2>
    <p>Connect models here. The Workforce Manager decides which model does each piece of work: free models first, paid ones only when the work needs them.</p></div>
   {view&&<p className="ai-models-usage" aria-label="Cloud usage this month">{usageLine(view)}</p>}
  </header>
  {error&&<p role="alert" className="ai-models-error">{error}</p>}
  {notice&&<p role="status" className="ai-models-notice">{notice}</p>}
  {busy.endsWith(':connect')&&<p role="status" className="ai-models-notice">Checking the key, choosing a model and testing it…</p>}
  {view&&!view.available&&<p role="alert" className="ai-models-error">Cloud model keys can only be entered on the Founder's own computer.</p>}
  {view&&<>
   <section aria-labelledby="ai-models-keys"><h3 id="ai-models-keys">1. Connect a cloud model</h3>
    <p className="ai-models-hint first">Paste the key and press Connect. AGO checks it, picks the best model, tests it and hands it to the Manager.</p>
    <ul className="ai-providers">{view.providers.map(p=>{
     const info=PROVIDER_INFO[p.provider],status=providerStatus(p),id='ai-'+p.provider,key=keyOf(p.provider);
     const list=p.models?.length?p.models:(p.model?[p.model]:[]);
     const picked=models[p.provider]??p.model??'';
     return <li key={p.provider} className="ai-provider" aria-label={info.name}>
      <div className="ai-provider-head"><strong>{info.name}</strong><span className={'ai-chip '+status.tone}>{status.text}</span>
       <a href={info.keyUrl} target="_blank" rel="noreferrer noopener">Get a key ↗</a></div>
      {p.last_error&&<p className="ai-models-error small">{errorText(p.last_error)}</p>}
      {p.saved&&<>
       <label htmlFor={id+'-model'}>Model</label>
       <select id={id+'-model'} value={picked} disabled={!editable} onChange={e=>setModels(old=>({...old,[p.provider]:e.target.value}))}>
        {list.map(m=><option key={m} value={m}>{m}</option>)}</select>
       {picked&&picked!==p.model&&<button type="button" className="ai-primary" disabled={!editable} onClick={()=>useModel(p.provider,picked)}>
        {busy===p.provider+':model'?'Testing…':'Use this model'}</button>}
      </>}
      <label htmlFor={id+'-key'}>{p.saved?'Replace key':'API key'}</label>
      <input id={id+'-key'} type="password" autoComplete="off" spellCheck={false} value={key} disabled={!view.available}
       placeholder={p.saved?'Saved '+p.key_hint:'Paste your key ('+info.keyLooks+')'}
       onChange={e=>setKey(p.provider,e.target.value)}/>
      {p.provider==='anthropic'&&(!p.saved||key.trim())&&<>
       <label htmlFor={id+'-workspace'}>Workspace ID (only if your key works across workspaces)</label>
       <input id={id+'-workspace'} value={workspace} autoComplete="off" spellCheck={false} disabled={!view.available}
        placeholder={p.workspace_id||'wrkspc_…'} onChange={e=>setWorkspace(e.target.value)}/>
      </>}
      <div className="ai-provider-actions">
       {(!p.saved||key.trim())&&<button type="button" className="ai-primary" disabled={!editable||!key.trim()} onClick={()=>connect(p.provider)} aria-label={'Connect '+info.name}>
        {busy===p.provider+':connect'?'Connecting…':'Connect'}</button>}
       {p.saved&&<button type="button" disabled={!editable} onClick={()=>test(p.provider)} aria-label={'Test '+info.name}>{busy===p.provider+':test'?'Testing…':'Test again'}</button>}
       {p.saved&&<button type="button" disabled={!editable} onClick={()=>remove(p.provider)} aria-label={'Remove '+info.name+' key'}>Remove</button>}
      </div>
     </li>;})}</ul>
   </section>
   <section aria-labelledby="ai-models-who"><h3 id="ai-models-who">2. The Manager decides</h3>
    <p className="ai-models-hint first">Code and skills need a capable model, so a small local model never writes code when a better one is connected. QA uses a capable model from a different provider when it can. Plans, Board votes and chat stay on free models. Work that already failed QA gets the strongest model.</p>
    <p className="ai-manager-pool" aria-label="Models the Manager can use"><b>Can use now:</b> {managerPool(view)}</p>
    <div className="ai-routes">
     <label className="ai-route"><span><b>Allow paid models</b><small>Claude and OpenAI cost money. Off means only free models are used.</small></span>
      <input type="checkbox" checked={Boolean(policy?.allow_paid)} disabled={!editable} onChange={e=>setPolicy(old=>({...old,allow_paid:e.target.checked}))}/></label>
     <label className="ai-route"><span><b>Monthly paid-call limit</b><small>Most paid calls per month. Free models are not counted.</small></span>
      <input type="number" min="0" max="5000" inputMode="numeric" value={policy?.monthly_call_cap??0} disabled={!editable}
       onChange={e=>setPolicy(old=>({...old,monthly_call_cap:e.target.value}))}/></label>
    </div>
    <button type="button" className="ai-primary" disabled={!editable} onClick={savePolicy}>{busy==='policy'?'Saving…':'Save'}</button>
    <h4>Recent choices</h4>
    {decisions.length?<ul className="ai-decisions" aria-label="Recent model choices">{decisions.slice(0,12).map(d=><li key={d.id}>
      <b>{d.work}</b>{d.role?' · '+d.role:''} → <span className={d.paid?'ai-chip warn':'ai-chip ok'}>{d.model}</span><small>{d.reason}</small></li>)}</ul>
     :<p className="ai-models-hint">No choices yet. They appear when AI work runs.</p>}
   </section>
   <p className="ai-models-foot">Keys stay encrypted on this computer, in AGO's private ~/.ago folder: never in the database or GitHub. The text of the work goes to the provider you choose. Each test is one call. Also set a spending limit in the provider's own dashboard.</p>
  </>}
 </div>;
}
