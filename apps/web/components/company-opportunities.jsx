"use client";
import {useCallback,useEffect,useState} from 'react';
const BASE='/v1/organization/company';
export function OpportunityRadar({api,me,onChanged}) {
 const [rows,setRows]=useState(null),[working,setWorking]=useState(false),[notice,setNotice]=useState('');
 const [expanded,setExpanded]=useState(false);
 const canRead=me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read');
 const canScan=me.roles?.includes('founder')&&me.permissions?.includes('organization:manage')&&me.permissions?.includes('brain:manage');
 const refresh=useCallback(async()=>{
  if(!canRead)return;
  try{const response=await api.request(BASE+'/opportunities');setRows(Array.isArray(response)?response:null);}
  catch{setRows(null);}
 },[api,canRead]);
 useEffect(()=>{refresh();const timer=setInterval(refresh,60000);return()=>clearInterval(timer);},[refresh]);
 async function scan(){
  if(!canScan||working)return;
  setWorking(true);setNotice('');
  try{
   const result=await api.request(BASE+'/opportunities/scan',{method:'POST'});
   setNotice(result.created?result.created+' business hypotheses sent to founder approvals.':
     result.reason==='delivery_running'?'Delivery work is running; no idle alert generated.':
     result.reason==='already_proposed_this_month'?'Current monthly ideas are already recorded.':
     'An active human founder must be configured before proposals can be generated.');
   await refresh();onChanged?.();
  }catch(e){setNotice(e.message||'Opportunity scan failed.');}
  finally{setWorking(false);}
 }
 if(!canRead)return null;
 return <section className="opportunity-radar" aria-label="Company opportunity radar">
  <header><div><h3>Company Opportunity Radar</h3>
    <p>Proactive business ideas, accountable management and founder-only approvals. No verified market demand or revenue is implied.</p></div>
    {canScan&&<button type="button" onClick={scan} disabled={working}>{working?'Checking…':'Scan business opportunities'}</button>}
  </header>
  {notice&&<p role="status">{notice}</p>}
  {rows===null?<p>Opportunity data unavailable or migration not applied.</p>:rows.length===0?
   <p>No recorded commercial hypotheses. An operator can run the scheduled idle-company scanner, or founder can scan manually.</p>:
   <>
    <p>{rows.filter(x=>x.approval_status==='pending').length} awaiting founder consideration · {rows.filter(x=>x.approval_status==='approved').length} approved for planning only</p>
    <button type="button" onClick={()=>setExpanded(v=>!v)}>{expanded?'Collapse':'Inspect'} commercial hypotheses</button>
    {expanded&&<div className="opportunity-items">{rows.map(o=><article key={o.id}>
     <strong>{o.title}</strong><small>Approval: {o.approval_status} · Management accountable: {o.accountable_manager_name}</small>
     {o.assignment_source==='founder_escalation'&&<small>Executive staffing gap — founder escalation</small>}
     <p><b>Potential customers:</b> {o.target_customer}</p>
     <p><b>Problem hypothesis:</b> {o.customer_problem}</p>
     <p><b>Proposed offer:</b> {o.proposed_offer}</p>
     <p><b>Revenue path (unverified):</b> {o.revenue_path}</p>
     <p><b>Before execution:</b> {o.validation_next_step}</p>
     <small>Catalog hypothesis only — not market-validated. Approval authorizes planning, not spending, emails, advertisements, or delivery.</small>
     <p><a href="#company-approval-inbox">Review scoped founder approval →</a></p>
    </article>)}</div>}
   </>}
 </section>;
}
