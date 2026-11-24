"use client";
import {useMemo,useState} from 'react';
import {buildWorkforceCorrections} from '@ago/sdk/workforce-corrections';

const BASE='/v1/organization/company';

/** ORG-016: the Brain's Employee Manager proposes matching designations and a
 * Founder → CEO → leadership → department heads → employees hierarchy. Nothing
 * changes until the Founder ticks rows and approves; each approved row uses the
 * existing founder-only role and manager endpoints, so identity, task history
 * and permissions stay as they are. */
export function WorkforceCorrections({api,me,employees,profiles,board,onSaved}){
 const founder=Boolean(me?.roles?.includes('founder'));
 const ready=Array.isArray(profiles)&&Array.isArray(employees);
 const {rows,notes}=useMemo(()=>ready?buildWorkforceCorrections({employees,profiles,board:board||[],founderId:me?.id}):{rows:[],notes:[]},
  [ready,employees,profiles,board,me?.id]);
 const [picked,setPicked]=useState({}),[busy,setBusy]=useState(false),[open,setOpen]=useState(false);
 const [message,setMessage]=useState(''),[failed,setFailed]=useState('');
 if(!founder)return null;
 const chosen=rows.filter(r=>picked[r.id]);
 const toggleAll=on=>setPicked(on?Object.fromEntries(rows.map(r=>[r.id,true])):{});
 async function approve(){
  if(busy||!chosen.length)return;
  setBusy(true);setMessage('');setFailed('');
  let done=0;
  try{
   // Rows come top of the tree first, so a head is in place before the
   // people who will report to them.
   for(const r of chosen){
    if(r.changes.includes('designation')){
     const extra=String(profiles.find(p=>p.id===r.id)?.extra_responsibilities||'').slice(0,3000);
     await api.request(BASE+'/employees/'+encodeURIComponent(r.id)+'/role',{method:'PUT',
      body:{role_title:r.proposed_title,core_responsibilities:r.proposed_core||r.proposed_title,extra_responsibilities:extra}});
    }
    if(r.changes.includes('reporting')){
     await api.request(BASE+'/employees/'+encodeURIComponent(r.id)+'/manager',{method:'PUT',body:{manager_id:r.proposed_manager_id}});
    }
    done++;
   }
   setMessage(done+' approved change'+(done===1?'':'s')+' saved. Names, task history and permissions are unchanged.');
   setPicked({});
  }catch(e){
   setFailed('Stopped after '+done+' saved. '+(e?.message||'A change was refused.')+' Refresh and look at the rest.');
  }finally{setBusy(false);await onSaved?.();}
 }
 return <section className="workforce-corrections" aria-labelledby="workforce-corrections-title">
  <h3 id="workforce-corrections-title">Employee Manager: fix designations and reporting</h3>
  <p>The Employee Manager compared every employee's name, designation and manager. Nothing changes until you tick the rows you agree with and press Approve. Names, task history and permissions are never changed.</p>
  {!ready&&<p role="alert">Employee records are unavailable, so no proposal can be made. Press Refresh.</p>}
  {ready&&!rows.length&&<p role="status">Everything matches. No change needed.</p>}
  {notes.map(n=><p key={n} className="workforce-note">{n}</p>)}
  {rows.length>0&&<>
   <p><strong>{rows.filter(r=>r.changes.includes('designation')).length}</strong> designations and <strong>{rows.filter(r=>r.changes.includes('reporting')).length}</strong> reporting lines to fix.</p>
   <button type="button" aria-expanded={open} onClick={()=>setOpen(v=>!v)}>{open?'Hide the proposal':'Review the proposal'}</button>
  </>}
  {open&&rows.length>0&&<>
   <div className="role-table-wrap" role="region" aria-label="Proposed workforce corrections" tabIndex={0}>
    <table><thead><tr>
     <th><input type="checkbox" aria-label="Select every change" checked={chosen.length===rows.length} onChange={e=>toggleAll(e.target.checked)}/></th>
     <th>Employee</th><th>Designation</th><th>Reports to</th><th>Why</th></tr></thead>
     <tbody>{rows.map(r=><tr key={r.id}>
      <td><input type="checkbox" aria-label={'Approve change for '+r.name} checked={Boolean(picked[r.id])} onChange={e=>setPicked(old=>({...old,[r.id]:e.target.checked}))}/></td>
      <td><strong>{r.name}</strong><small>{r.area}</small></td>
      <td>{r.changes.includes('designation')?<><s>{r.current_title}</s> → <b>{r.proposed_title}</b></>:r.current_title}</td>
      <td>{r.changes.includes('reporting')?<><s>{r.current_manager_name}</s> → <b>{r.proposed_manager_name}</b></>:r.current_manager_name}</td>
      <td><small>{r.reason}</small></td>
     </tr>)}</tbody></table>
   </div>
   <button type="button" className="workforce-approve" disabled={busy||!chosen.length} onClick={approve}>
    {busy?'Saving…':'Approve '+chosen.length+' selected change'+(chosen.length===1?'':'s')}</button>
  </>}
  {message&&<p role="status">{message}</p>}{failed&&<p role="alert">{failed}</p>}
 </section>;
}
