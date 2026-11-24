"use client";
import {useCallback,useEffect,useState} from 'react';
import {PROVIDER_INFO,ROUTE_INFO,errorText,providerStatus,routable,routeSummary,settingsView,usageLine} from './ai-models-state';

const BASE='/v1/organization/company';

/** Founder's AI model settings: Ollama does everything by default; a tested
 * cloud model can take over code writing, QA review or Board chat. Keys are
 * write-only: after Save the browser never sees them again. */
export function AiModels({api,me,active=true}){
 const founder=Boolean(me?.roles?.includes('founder'));
 const [view,setView]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [drafts,setDrafts]=useState({}),[models,setModels]=useState({}),[busy,setBusy]=useState('');
 const [routes,setRoutes]=useState(null);
 const apply=useCallback(raw=>{
  const next=settingsView(raw);
  if(!next)throw new Error('AI model settings could not be read. Press Refresh.');
  setView(next);setRoutes({code:next.routes.code??null,qa:next.routes.qa??null,chat:next.routes.chat??null,monthly_call_cap:next.monthly_call_cap});
 },[]);
 useEffect(()=>{
  if(!founder||!active)return undefined;
  let live=true;
  api.request(BASE+'/cloud-models').then(v=>{if(live){apply(v);setError('');}})

   .catch(e=>{if(live)setError(e?.message||'AI model settings are unavailable.');});
  return()=>{live=false;};
 },[api,founder,active,apply]);
 if(!founder)return <div className="ai-models"><h2>AI models</h2><p>Only the Founder can add or change AI models.</p></div>;
 const draft=name=>drafts[name]||{model:view?.providers.find(p=>p.provider===name)?.model||'',key:''};
 const setDraft=(name,patch)=>setDrafts(old=>({...old,[name]:{...draft(name),...patch}}));
 async function act(label,work,done){
  setBusy(label);setError('');setNotice('');
  try{const result=await work();if(result?.providers)apply(result);if(done)done(result);}
  catch(e){setError(e?.message||'That did not work.');}
  finally{setBusy('');}
 }
 const save=name=>act(name+':save',()=>api.request(BASE+'/cloud-models/'+name,{method:'PUT',body:{model:draft(name).model.trim(),api_key:draft(name).key.trim()||null}}),
  ()=>{setDraft(name,{key:''});setNotice(PROVIDER_INFO[name].name+' saved. Press Test to check it.');});
 const test=name=>act(name+':test',()=>api.request(BASE+'/cloud-models/'+name+'/test',{method:'POST',body:{},timeoutMs:65000}),
  r=>setNotice(r.test.ok?PROVIDER_INFO[name].name+' works. You can now choose it below.':PROVIDER_INFO[name].name+': '+errorText(r.test.code)));
 const load=name=>act(name+':models',()=>api.request(BASE+'/cloud-models/'+name+'/models',{timeoutMs:30000}),
  r=>{setModels(old=>({...old,[name]:r.models}));setNotice(r.models.length+' models found for '+PROVIDER_INFO[name].name+'. Pick one and press Save.');});
 const remove=name=>act(name+':remove',()=>api.request(BASE+'/cloud-models/'+name,{method:'DELETE'}),
  ()=>setNotice(PROVIDER_INFO[name].name+' key removed from this computer.'));
 const saveRoutes=()=>act('routes',()=>api.request(BASE+'/cloud-model-routes',{method:'PUT',body:{...routes,monthly_call_cap:Number(routes.monthly_call_cap)}}),
  ()=>setNotice('Saved. AGO uses these models from the next AI task.'));
 const ready=routable(view);
 return <div className="ai-models">
  <header className="ai-models-head">
   <div><h2>AI models</h2>
    <p>The local model (Ollama) does all work by default, for free. Add a cloud model for work that needs a stronger brain.</p></div>
   {view&&<p className="ai-models-usage" aria-label="Cloud usage this month">{usageLine(view)}</p>}
  </header>
  {error&&<p role="alert" className="ai-models-error">{error}</p>}
  {notice&&<p role="status" className="ai-models-notice">{notice}</p>}
  {view&&!view.available&&<p role="alert" className="ai-models-error">Cloud model keys can only be entered on the Founder's own computer.</p>}
  {view&&<>
   <section aria-labelledby="ai-models-who"><h3 id="ai-models-who">Which model does which work</h3>
    <div className="ai-routes">
     {ROUTE_INFO.map(r=><label key={r.route} className="ai-route"><span><b>{r.label}</b><small>{r.help}</small></span>
      <select value={routes?.[r.route]||''} disabled={!view.available} onChange={e=>setRoutes(old=>({...old,[r.route]:e.target.value||null}))}>
       <option value="">Local model (Ollama)</option>
       {ready.map(p=><option key={p.provider} value={p.provider}>{PROVIDER_INFO[p.provider].name} · {p.model}</option>)}
      </select></label>)}
     <label className="ai-route"><span><b>Monthly limit</b><small>Most cloud calls per month. 0 turns cloud models off.</small></span>
      <input type="number" min="0" max="5000" inputMode="numeric" value={routes?.monthly_call_cap??0} disabled={!view.available}
       onChange={e=>setRoutes(old=>({...old,monthly_call_cap:e.target.value}))}/></label>
    </div>
    {!ready.length&&<p className="ai-models-hint">Add a key below and press Test. Then you can choose it here.</p>}
    <button type="button" className="ai-primary" disabled={!view.available||busy==='routes'} onClick={saveRoutes}>{busy==='routes'?'Saving…':'Save choices'}</button>
    <ul className="ai-route-now" aria-label="Now in use">{routeSummary(view).map(r=><li key={r.route}>{r.label}: <b>{r.uses}</b></li>)}</ul>
   </section>
   <section aria-labelledby="ai-models-keys"><h3 id="ai-models-keys">Cloud model keys</h3>
    <ul className="ai-providers">{view.providers.map(p=>{
     const info=PROVIDER_INFO[p.provider],status=providerStatus(p),d=draft(p.provider),id='ai-'+p.provider;
     return <li key={p.provider} className="ai-provider" aria-label={info.name}>
      <div className="ai-provider-head"><strong>{info.name}</strong><span className={'ai-chip '+status.tone}>{status.text}</span>
       <a href={info.keyUrl} target="_blank" rel="noreferrer noopener">Get a key ↗</a></div>
      {p.last_error&&<p className="ai-models-error small">{errorText(p.last_error)}</p>}
      <label htmlFor={id+'-key'}>API key</label>
      <input id={id+'-key'} type="password" autoComplete="off" spellCheck={false} value={d.key} disabled={!view.available}
       placeholder={p.saved?'Saved '+p.key_hint+' · paste to replace':'Paste your key ('+info.keyLooks+')'}
       onChange={e=>setDraft(p.provider,{key:e.target.value})}/>
      <label htmlFor={id+'-model'}>Model</label>
      <input id={id+'-model'} list={id+'-list'} value={d.model} disabled={!view.available} placeholder={info.example}
       onChange={e=>setDraft(p.provider,{model:e.target.value})}/>
      <datalist id={id+'-list'}>{(models[p.provider]||[]).map(m=><option key={m} value={m}/>)}</datalist>
      <div className="ai-provider-actions">
       <button type="button" className="ai-primary" disabled={!view.available||busy!==''||!d.model.trim()||(!p.saved&&!d.key.trim())} onClick={()=>save(p.provider)}>{busy===p.provider+':save'?'Saving…':'Save'}</button>
       <button type="button" disabled={!p.saved||busy!==''} onClick={()=>load(p.provider)}>{busy===p.provider+':models'?'Loading…':'Load models'}</button>
       <button type="button" disabled={!p.saved||busy!==''} onClick={()=>test(p.provider)} aria-label={'Test '+info.name}>{busy===p.provider+':test'?'Testing…':'Test'}</button>
       {p.saved&&<button type="button" disabled={busy!==''} onClick={()=>remove(p.provider)} aria-label={'Remove '+info.name+' key'}>Remove</button>}
      </div>
     </li>;})}</ul>
   </section>
   <p className="ai-models-foot">Keys stay encrypted on this computer, in AGO's private ~/.ago folder: never in the database or GitHub. The text of the work goes to the provider you choose. Test counts as one call. Also set a spending limit in the provider's own dashboard.</p>
  </>}
 </div>;
}
