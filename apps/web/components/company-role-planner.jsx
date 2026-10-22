"use client";
import {useMemo,useState} from 'react';
import {buildCompanyRolePlan,buildLeadershipPlan} from '@ago/sdk/company-roles';

const BASE='/v1/organization/company';
export function CompanyRolePlanner({api,me,employees,departments,profiles,board=[],onSaved}){
 const [expanded,setExpanded]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[failed,setFailed]=useState('');
 const eligible=me.roles?.includes('founder')&&me.permissions?.includes('organization:manage');
 const profilesReady=Array.isArray(profiles);
 const plan=useMemo(()=>profilesReady?buildCompanyRolePlan(employees,departments,profiles,me.id):[],[employees,departments,profiles,me.id,profilesReady]);
 const candidates=plan.filter(p=>p.status==='proposed');
 const executivePlan=useMemo(()=>buildLeadershipPlan(employees,profiles,board,me.id),[employees,profiles,board,me.id]);
 const [executiveBusy,setExecutiveBusy]=useState(false);
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
 async function establishHierarchy(){
   if(executiveBusy||!eligible||!profilesReady)return;
   setExecutiveBusy(true);setFailed('');setMessage('');
   let savedRoles=0,savedSeats=0,reporting=0;
   try{
    // A single founder-authorized bulk action over existing employees only.
    const ceo=executivePlan[0];
    for(const item of executivePlan){
      if(!item.employee_id)continue;
      const existing=profiles.find(p=>p.id===item.employee_id);
      const detail=existing?.extra_responsibilities||'';
      await api.request(BASE+'/employees/'+encodeURIComponent(item.employee_id)+'/role',{
       method:'PUT',body:{
        role_title:item.title,
        core_responsibilities:item.work,
        extra_responsibilities:detail+' | Executive assignment explicitly reviewed by founder. CEO responsible after founder approves a project.'
       }
      });
      savedRoles++;
      await api.request(BASE+'/board/appoint',{method:'POST',body:{seat:item.seat,employee_id:item.employee_id}});
      savedSeats++;
    }
    // Do not overwrite custom staff roles or reporting relationships.
    for(const item of candidates){
      if(executivePlan.some(e=>e.employee_id===item.id))continue;
      await api.request(BASE+'/employees/'+encodeURIComponent(item.id)+'/role',{
       method:'PUT',body:{role_title:item.role_title,core_responsibilities:item.core_responsibilities,
        extra_responsibilities:item.extra_responsibilities}
      });
      savedRoles++;
    }
    if(ceo?.employee_id){
      for(const employee of employees){
        if(employee.id===me.id)continue;
        if(employee.id===ceo.employee_id){
          if(employee.manager_id!==me.id){
           await api.request(BASE+'/employees/'+encodeURIComponent(employee.id)+'/manager',{
            method:'PUT',body:{manager_id:me.id}
           });reporting++;
          }
        }else if(!employee.manager_id){
          await api.request(BASE+'/employees/'+encodeURIComponent(employee.id)+'/manager',{
           method:'PUT',body:{manager_id:ceo.employee_id}
          });reporting++;
        }
      }
    }
    setMessage('Saved '+savedRoles+' real employee roles, '+savedSeats+' board seats and '+reporting+' missing reporting links. No AI task was executed.');
   }catch(e){
    setFailed('Some records were saved before interruption: '+savedRoles+' roles, '+savedSeats+' seats, '+reporting+' reporting links. '+e.message+'. Refresh and inspect; repeated board appointments are idempotent.');
   }finally{setExecutiveBusy(false);await onSaved?.();}
 }
 if(!eligible)return null;
 return <section id="ago-role-planner" className="company-role-planner" aria-label="Company workforce expertise and roles">
  <h3>Company Role & Expertise Planner</h3>
  <p>Complete departmental coverage for the actual recorded workforce. Each employee has a proposed specialization, work area, deliverables and escalation expectations. Proposals are not evidence of existing skills or permission to start work.</p>
  {!profilesReady&&<p role="alert">Employee accountability records are unavailable. Bulk assignment is disabled to protect existing role profiles.</p>}
  <p><strong>{plan.length}</strong> employees in the company · <strong>{plan.length-candidates.length}</strong> already profiled · <strong>{candidates.length}</strong> missing defined responsibilities</p>
  <button type="button" onClick={()=>setExpanded(v=>!v)} aria-expanded={expanded}>{expanded?'Hide all roles':'Inspect roles and expertise'}</button>
  <button type="button" disabled={!profilesReady||!candidates.length||busy} onClick={apply}>{busy?'Saving verified company records…':'Assign '+candidates.length+' missing role profiles'}</button>
  <section className="company-executive-staffing" aria-label="CEO and leadership staffing">
   <h4>Executive leadership · one accountable CEO</h4>
   <p>CEO receives operational accountability after the Founder approves full project scope. CTO, CFO, CISO and CQO report to CEO. Appointments here do not grant login credentials, payments or deployment privileges.</p>
   <div className="role-table-wrap"><table><thead><tr><th>Board responsibility</th><th>Executive position</th><th>Actual candidate</th><th>Assignment</th></tr></thead><tbody>
    {executivePlan.map(x=><tr key={x.seat}><td>{x.seat}</td><td><strong>{x.title}</strong><small>{x.work}</small></td><td>{x.employee_name}</td><td>{x.existing?'Recorded seat':'Founder review required'}</td></tr>)}
   </tbody></table></div>
   <button type="button" disabled={!profilesReady||!executivePlan[0]?.employee_id||executiveBusy||busy} onClick={establishHierarchy}>{executiveBusy?'Recording actual company roles…':'Apply workforce roles + CEO/CTO/Board hierarchy'}</button>
   <small>Explicit founder action overwrites executive job titles selected above; other meaningful existing profiles are preserved. Vacant roles remain visible, never fake-staffed.</small>
  </section>
  <small>Existing assigned responsibility profiles are preserved. This records duties only, not board seats, RBAC, verified competence, tasks or an always-on AI worker.</small>
  {message&&<p role="status">{message}</p>}{failed&&<p role="alert">{failed}</p>}
  {expanded&&<div className="role-table-wrap"><table><thead><tr><th>Employee</th><th>Department & reporting</th><th>Role / work area</th><th>Specialization focus</th><th>Record</th></tr></thead><tbody>
   {plan.map(p=><tr key={p.id}><td>{p.name} <small>({p.kind})</small></td><td>{p.department}{p.manager_id&&<small> · manager recorded</small>}</td><td><b>{p.role_title}</b><small>{p.core_responsibilities}</small></td><td>{p.focus}</td><td className="role-status">{p.status==='configured'?'Existing profile retained':'Proposed profile'}</td></tr>)}
  </tbody></table></div>}
 </section>;
}
