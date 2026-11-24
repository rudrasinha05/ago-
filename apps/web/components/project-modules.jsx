"use client";
import {useCallback,useEffect,useState} from 'react';
import {modulesSummary,modulesView} from './project-modules-state';

/** PROJ-014/016: the project's module plan. The Founder approves it once;
 * then AGO builds the working prototype and each module, tests every unit
 * together with everything integrated before it, and only then integrates it.
 * Approving starts nothing by itself: every task still needs its approval. */
export function ProjectModules({api,project,onChanged}){
 const base='/v1/organization/company/projects/'+encodeURIComponent(project.id)+'/modules';
 const [view,setView]=useState(null),[error,setError]=useState(''),[busy,setBusy]=useState(false),[notice,setNotice]=useState('');
 const load=useCallback(()=>api.request(base).then(raw=>{
  const v=modulesView(raw);
  if(!v)throw new Error('The module plan could not be read.');
  setView(v);setError('');
 }).catch(e=>setError(e?.message||'The module plan is unavailable.')),[api,base]);
 useEffect(()=>{load();},[load]);
 async function approve(){
  setBusy(true);setError('');setNotice('');
  try{
   const v=modulesView(await api.request(base+'/approve',{method:'POST',body:{}}));
   if(!v)throw new Error('The module plan could not be read.');
   setView(v);setNotice('Module plan approved. The AI project manager starts with the working prototype on the next step; each task still needs approval before it runs.');
   onChanged?.();
  }catch(e){setError(e?.message||'Approval did not work.');}
  finally{setBusy(false);}
 }
 const units=view?.units.length?view.units:view?.preview.map(m=>({...m,label:'Not planned yet'}))||[];
 return <section className="project-modules" aria-labelledby={'project-modules-'+project.id}>
  <h5 id={'project-modules-'+project.id}>Prototype and modules</h5>
  <button type="button" className="project-module-refresh" onClick={()=>{setNotice('');load();}}>Refresh</button>
  {error&&<p role="alert">{error}</p>}
  {view&&<p>{modulesSummary(view)}</p>}
  {notice&&<p role="status">{notice}</p>}
  {units.length>0&&<ol className="project-module-list" aria-label="Module plan">
   {units.map(u=><li key={u.code} className={'project-module '+(u.status||'preview')}>
    <b>{u.code==='PROTOTYPE'?'Prototype':u.code}</b> {u.title}
    <span className="project-module-status">{u.label}{u.status==='integrated'&&u.unittest_cases?' · '+u.unittest_cases+' tests passed together':''}</span>
   </li>)}
  </ol>}
  {view?.deferred.length>0&&<p className="project-module-deferred">Deferred for later: {view.deferred.join(', ')}</p>}
  {view?.status==='proposed'&&<button type="button" className="project-module-approve" disabled={busy} onClick={approve}>
   {busy?'Approving…':'Approve module plan'}</button>}
  {view?.latest&&<p className="project-module-source"><small>Integrated source: version {view.latest.version}, {view.latest.files} files, {view.latest.unittest_cases} tests passed together in offline Docker.</small></p>}
 </section>;
}
