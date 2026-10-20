"use client";
import {useEffect,useState} from 'react';

export function RoleEditor({employee,profile,api,canManage,onSaved}) {
 const [title,setTitle]=useState(profile?.role_title||'');
 const [core,setCore]=useState(profile?.core_responsibilities||'');
 const [extra,setExtra]=useState(profile?.extra_responsibilities||'');
 const [error,setError]=useState(''),[working,setWorking]=useState(false),[editing,setEditing]=useState(false);
 useEffect(()=>{setTitle(profile?.role_title||'');setCore(profile?.core_responsibilities||'');setExtra(profile?.extra_responsibilities||'');},[profile?.role_title,profile?.core_responsibilities,profile?.extra_responsibilities]);
 async function save(e){e.preventDefault();setWorking(true);setError('');
   try{await api.request('/v1/organization/company/employees/'+encodeURIComponent(employee.id)+'/role',
          {method:'PUT',body:{role_title:title,core_responsibilities:core,extra_responsibilities:extra}});
       await onSaved();setEditing(false);}
   catch(err){setError(err.message);}finally{setWorking(false);}
 }
 return <section className="accountability-panel">
  <h4>Recorded responsibilities</h4>
  <dl><dt>Role title</dt><dd>{profile?.role_title||'Not assigned'}</dd>
  <dt>Core duties</dt><dd>{profile?.core_responsibilities||'Not configured'}</dd>
  <dt>Extra duties</dt><dd>{profile?.extra_responsibilities||'Not configured'}</dd></dl>
  {canManage&&<button type="button" onClick={()=>setEditing(v=>!v)}>{editing?'Cancel editing':'Edit employee accountability'}</button>}
  {editing&&canManage&&<form onSubmit={save} className="accountability-form">
    <label>Official role title<input value={title} onChange={e=>setTitle(e.target.value)} maxLength={150} required/></label>
    <label>Core responsibilities<textarea value={core} onChange={e=>setCore(e.target.value)} maxLength={3000} required/></label>
    <label>Additional responsibilities<textarea value={extra} onChange={e=>setExtra(e.target.value)} maxLength={3000}/></label>
    <button disabled={working||!title.trim()||!core.trim()}>{working?'Saving…':'Save role details'}</button>
  </form>}
  {error&&<p role="alert">{error}</p>}
 </section>;
}

const TYPES=[['doubt','Doubt / question'],['blocker','Blocker'],['module_complete','Module completed'],['phase_complete','Phase completed']];
export function UpwardReports({api,me,employees,onRecorded}) {
 const current=employees.find(e=>e.id===me.id);
 const canSend=Boolean(current&&current.kind==='human'&&!me.roles.includes('founder'));
 const [kind,setKind]=useState('doubt'),[body,setBody]=useState('');
 const [reports,setReports]=useState(null),[error,setError]=useState(''),[saving,setSaving]=useState(false);
 const refresh=async()=>{try{setReports(await api.request('/v1/organization/company/reports'));}catch{setReports(null);}};
 useEffect(()=>{refresh();},[api]);
 async function submit(e){e.preventDefault();setSaving(true);setError('');
   try{await api.request('/v1/organization/company/reports',{method:'POST',
         body:{kind,body,operation_key:crypto.randomUUID(),task_id:null}});
       setBody('');await refresh();await onRecorded();}
   catch(err){setError(err.message);}finally{setSaving(false);}
 }
 return <section className="upward-reports" aria-label="Company reporting chain">
   <div><h3>Hierarchy reporting</h3>
    <p>Doubts, blockers and completed modules go to the immediate manager, or the founder for department-root employees. Details are limited to sender, recipient and founder.</p>
   </div>
   {canSend&&<form onSubmit={submit} className="accountability-form">
     <label>Report type<select value={kind} onChange={e=>setKind(e.target.value)}>{TYPES.map(([value,label])=><option value={value} key={value}>{label}</option>)}</select></label>
     <label>Report to {employees.find(e=>e.id===current.manager_id)?.name||'Founder'}<textarea required rows={3} maxLength={6000} value={body} onChange={e=>setBody(e.target.value)} placeholder="Progress, evidence, questions or blockers"/></label>
     <button disabled={saving||!body.trim()}>{saving?'Submitting…':'Submit to immediate superior'}</button>
   </form>}
   <div className="report-inbox"><h4>{me.roles.includes('founder')?'Company report inbox':'My reports and inbox'}</h4>
    {reports===null?<p>Report history unavailable or access restricted.</p>:!reports.length?<p>No verified reporting events yet.</p>:
       reports.slice(0,8).map(r=><article key={r.id}><strong>#{r.id} · {r.kind.replaceAll('_',' ')}</strong><small>From {employees.find(e=>e.id===r.author_id)?.name||'Employee'} → {employees.find(e=>e.id===r.recipient_id)?.name||'Founder'}</small><p>{r.body}</p></article>)}
   </div>{error&&<p role="alert">{error}</p>}
 </section>;
}
