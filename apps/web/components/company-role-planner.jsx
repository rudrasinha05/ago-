"use client";
import {useMemo,useState} from 'react';
import {buildCompanyRolePlan,buildLeadershipPlan} from '@ago/sdk/company-roles';

const BASE='/v1/organization/company';
export function CompanyRolePlanner({api,me,employees,departments,profiles,board=[],onSaved}){
 const [expanded,setExpanded]=useState(false),[busy,setBusy]=useState(false),[message,setMessage]=useState(''),[failed,setFailed]=useState('');
 const [hierarchyOpen,setHierarchyOpen]=useState(false),[managerChoices,setManagerChoices]=useState({}),[linkSaving,setLinkSaving]=useState(null);
 const eligible=me.roles?.includes('founder')&&me.permissions?.includes('organization:manage');
 const profilesReady=Array.isArray(profiles);
 const plan=useMemo(()=>profilesReady?buildCompanyRolePlan(employees,departments,profiles,me.id):[],[employees,departments,profiles,me.id,profilesReady]);
 const candidates=plan.filter(p=>p.status==='proposed');
 const executivePlan=useMemo(()=>buildLeadershipPlan(employees,profiles,board,me.id,departments),[employees,profiles,board,me.id,departments]);
 const [executiveBusy,setExecutiveBusy]=useState(false);
 const byId=new Map(employees.map(e=>[e.id,e]));
 const chiefId=executivePlan[0]?.employee_id;
 const chiefIds=new Set(executivePlan.filter(e=>e.employee_id).map(e=>e.employee_id));
 const unreviewedCeoReports=employees.filter(e=>e.id!==me.id&&e.manager_id===chiefId&&!chiefIds.has(e.id));
 const currentManagerName=id=>id===me.id?'Founder':byId.get(id)?.name||'Department root / unresolved';
 async function saveReviewedManager(employee){
   if(!eligible||linkSaving||!profilesReady)return;
   const target=managerChoices[employee.id];
   if(!target||target===employee.id||target===employee.manager_id)return;
   if(!employees.some(e=>e.id===target))return;
   setLinkSaving(employee.id);setFailed('');setMessage('');
   try{
     await api.request(BASE+'/employees/'+encodeURIComponent(employee.id)+'/manager',{
       method:'PUT',body:{manager_id:target}
     });
     setMessage('Founder-reviewed manager link saved for '+employee.name+'.');
     setManagerChoices(old=>({...old,[employee.id]:undefined}));
     await onSaved?.();
   }catch(e){setFailed('Reporting change refused: '+e.message);}
   finally{setLinkSaving(null);}
 }
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
      // Never blanket-attach staff from unrelated departments to CEO.
      for(const item of executivePlan){
        if(!item.employee_id)continue;
        const worker=employees.find(e=>e.id===item.employee_id);
        const managerId=item.seat==='Strategy & Vision'?me.id:ceo.employee_id;
        if(worker&&!worker.manager_id&&worker.id!==managerId){
          await api.request(BASE+'/employees/'+encodeURIComponent(worker.id)+'/manager',{
            method:'PUT',body:{manager_id:managerId}
          });reporting++;
        }
      }
    }
    setMessage('Saved '+savedRoles+' profiles, '+savedSeats+' Board seats and '+reporting+' executive links. Other manager links remain subject to individual Founder review; no AI task executed.');
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
   <div className="role-table-wrap" role="region" aria-label="Scrollable executive role assignments" tabIndex={0}><table><thead><tr><th>Board responsibility</th><th>Executive position</th><th>Actual candidate</th><th>Assignment</th></tr></thead><tbody>
    {executivePlan.map(x=><tr key={x.seat}><td>{x.seat}</td><td><strong>{x.title}</strong><small>{x.work}</small></td><td>{x.employee_name}</td><td>{x.existing?'Recorded seat':'Founder review required'}</td></tr>)}
   </tbody></table></div>
   <button type="button" disabled={!profilesReady||!executivePlan[0]?.employee_id||executiveBusy||busy} onClick={establishHierarchy}>{executiveBusy?'Recording actual company roles…':'Apply workforce roles + CEO/CTO/Board hierarchy'}</button>
   <small>Explicit founder action overwrites executive job titles selected above; other meaningful existing profiles are preserved. Vacant roles remain visible, never fake-staffed.</small>
  </section>
  <section className="company-reporting-audit" aria-label="Recorded reporting link audit">
   <h4>Reporting audit — current manager links</h4>
   <p>{unreviewedCeoReports.length} non-Board employees currently report directly to CEO. These are recorded links, not proof the assignment is correct. A previous bulk action may have connected unrelated workers. Review each before changing.</p>
   <button type="button" aria-expanded={hierarchyOpen} onClick={()=>setHierarchyOpen(v=>!v)}>{hierarchyOpen?'Hide reporting audit':'Review employee reporting links'}</button>
   {hierarchyOpen&&<div className="role-table-wrap" role="region" aria-label="Employee manager review" tabIndex={0}>
    <table><thead><tr><th>Employee / role</th><th>Recorded manager</th><th>Choose actual manager</th><th>Founder action</th></tr></thead>
     <tbody>{employees.filter(e=>e.id!==me.id).map(e=>{
       const picked=managerChoices[e.id]??e.manager_id??'';
       return <tr key={e.id}><td><strong>{e.name}</strong><small>{profiles?.find(p=>p.id===e.id)?.role_title||'Role unassigned'}</small></td>
         <td>{currentManagerName(e.manager_id)}</td>
         <td><select aria-label={'Reviewed manager for '+e.name} value={picked}
          onChange={event=>setManagerChoices(old=>({...old,[e.id]:event.target.value}))}>
           <option value="">No manager chosen</option>
           {employees.filter(b=>b.id!==e.id).map(b=><option key={b.id} value={b.id}>{b.name}</option>)}
         </select></td>
         <td><button type="button" onClick={()=>saveReviewedManager(e)}
           disabled={!picked||picked===e.manager_id||linkSaving!==null}>{linkSaving===e.id?'Saving…':'Save reviewed link'}</button></td>
       </tr>;
     })}</tbody>
    </table>
   </div>}
  </section>
  <small>Existing assigned responsibility profiles are preserved. This records duties only, not board seats, RBAC, verified competence, tasks or an always-on AI worker.</small>
  {message&&<p role="status">{message}</p>}{failed&&<p role="alert">{failed}</p>}
  {expanded&&<div className="role-table-wrap" role="region" aria-label="Scrollable employee expertise table" tabIndex={0}><table><thead><tr><th>Employee</th><th>Department & reporting</th><th>Role / work area</th><th>Specialization focus</th><th>Record</th></tr></thead><tbody>
   {plan.map(p=><tr key={p.id}><td>{p.name} <small>({p.kind})</small></td><td>{p.department}{p.manager_id&&<small> · manager recorded</small>}</td><td><b>{p.role_title}</b><small>{p.core_responsibilities}</small></td><td>{p.focus}</td><td className="role-status">{p.status==='configured'?'Existing profile retained':'Proposed profile'}</td></tr>)}
  </tbody></table></div>}
 </section>;
}
