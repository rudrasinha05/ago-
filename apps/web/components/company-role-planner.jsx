"use client";
import {useMemo,useState} from 'react';
import {buildCompanyRolePlan} from '@ago/sdk/company-roles';

const BASE='/v1/organization/company';
export function CompanyRolePlanner({api,me,employees,departments,profiles,onSaved}){
 const [expanded,setExpanded]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[failed,setFailed]=useState('');
 const eligible=me.roles?.includes('founder')&&me.permissions?.includes('organization:manage');
 const profilesReady=Array.isArray(profiles);
 const plan=useMemo(()=>profilesReady?buildCompanyRolePlan(employees,departments,profiles,me.id):[],[employees,departments,profiles,me.id,profilesReady]);
 const candidates=plan.filter(p=>p.status==='proposed');
 async function apply(){
  if(busy||!eligible||!profilesReady||!candidates.length)return;
  setBusy(true);setFailed('');setMessage('');
  let saved=0;
  try{
   for(const item of candidates){
    await api.request(BASE+'/employees/'+encodeURIComponent(item.id)+'/role',{
     method:'PUT',body:{role_title:item.role_title,core_responsibilities:item.core_responsibilities,extra_responsibilities:item.extra_responsibilities}
    });saved++;
   }
   setMessage(saved+' real employee role profiles saved. No virtual task, privilege or AI run was created.');
  }catch(err){
   setFailed('Stopped after '+saved+' saved profiles. '+err.message+'. Refresh to inspect remaining employees; saved profiles will be skipped on retry.');
  }finally{
   setBusy(false);await onSaved?.();
  }
 }
 if(!eligible)return null;
 return <section id="ago-role-planner" className="company-role-planner" aria-label="Company workforce expertise and roles">
  <h3>Company Role & Expertise Planner</h3>
  <p>Complete departmental coverage for the actual recorded workforce. Each employee has a proposed specialization, work area, deliverables and escalation expectations. Proposals are not evidence of existing skills or permission to start work.</p>
  {!profilesReady&&<p role="alert">Employee accountability records are unavailable. Bulk assignment is disabled to protect existing role profiles.</p>}
  <p><strong>{plan.length}</strong> employees in the company · <strong>{plan.length-candidates.length}</strong> already profiled · <strong>{candidates.length}</strong> missing defined responsibilities</p>
  <button type="button" onClick={()=>setExpanded(v=>!v)} aria-expanded={expanded}>{expanded?'Hide all roles':'Inspect roles and expertise'}</button>
  <button type="button" disabled={!profilesReady||!candidates.length||busy} onClick={apply}>{busy?'Saving verified company records…':'Assign '+candidates.length+' missing role profiles'}</button>
  <small>Existing assigned responsibility profiles are preserved. This records duties only, not board seats, RBAC, verified competence, tasks or an always-on AI worker.</small>
  {message&&<p role="status">{message}</p>}{failed&&<p role="alert">{failed}</p>}
  {expanded&&<div className="role-table-wrap"><table><thead><tr><th>Employee</th><th>Department & reporting</th><th>Role / work area</th><th>Specialization focus</th><th>Record</th></tr></thead><tbody>
   {plan.map(p=><tr key={p.id}><td>{p.name} <small>({p.kind})</small></td><td>{p.department}{p.manager_id&&<small> · manager recorded</small>}</td><td><b>{p.role_title}</b><small>{p.core_responsibilities}</small></td><td>{p.focus}</td><td className="role-status">{p.status==='configured'?'Existing profile retained':'Proposed profile'}</td></tr>)}
  </tbody></table></div>}
 </section>;
}
