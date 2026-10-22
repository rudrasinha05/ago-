"use client";
import {useCallback,useEffect,useState} from 'react';

const BASE='/v1/organization/company';
const safeUrl=value=>{try{const x=new URL(value);return x.protocol==='https:'&&!x.username&&!x.password?x.href:null;}catch{return null;}};
const dated=value=>value?new Date(value).toLocaleString():'Not reported';

export function OpportunityRadar({api,me,onChanged}) {
 const [rows,setRows]=useState(null),[market,setMarket]=useState(null);
 const [working,setWorking]=useState(false),[notice,setNotice]=useState('');
 const [promoting,setPromoting]=useState(null);
 const [expanded,setExpanded]=useState(false),[signalsOpen,setSignalsOpen]=useState(true);
 const [draftsOpen,setDraftsOpen]=useState(false),[signalFilter,setSignalFilter]=useState('all');
 const canRead=me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read');
 const canScan=me.roles?.includes('founder')&&me.permissions?.includes('organization:manage')&&me.permissions?.includes('brain:manage');
 const refresh=useCallback(async()=>{
  if(!canRead)return;
  const [known,discovery]=await Promise.allSettled([
   api.request(BASE+'/opportunities'),
   api.request(BASE+'/market-intelligence?limit=200'),
  ]);
  setRows(known.status==='fulfilled'&&Array.isArray(known.value)?known.value:null);
  setMarket(discovery.status==='fulfilled'&&discovery.value?.signals?discovery.value:null);
 },[api,canRead]);
 useEffect(()=>{refresh();const timer=setInterval(refresh,60000);return()=>clearInterval(timer);},[refresh]);
 async function scan(){
  if(!canScan||working)return;
  setWorking(true);setNotice('');
  try{
   const result=await api.request(BASE+'/opportunities/scan',{method:'POST'});
   setNotice(result.created?result.created+' catalog hypotheses sent to founder approvals.':
     result.reason==='delivery_running'?'A delivery task is running; catalog suggestions paused. Internet research runs separately.':
     result.reason==='already_proposed_this_month'?'Monthly catalog already covered. Internet research runs separately.':
     'An active human founder must be configured.');
   await refresh();onChanged?.();
  }catch(e){setNotice(e.message||'Catalog scan failed.');}
  finally{setWorking(false);}
 }
 async function promote(signal){
  if(!canScan||promoting)return;
  setPromoting(signal.id);setNotice('');
  try{
   const project=await api.request(BASE+'/market-intelligence/'+encodeURIComponent(signal.id)+'/project',{method:'POST'});
   setNotice('Founder-approved signal linked to project draft: '+project.title+'. Delivery still requires a reviewed and staffed plan.');
   await refresh();onChanged?.();
   document.getElementById('ago-project-portfolio')?.scrollIntoView({behavior:'smooth'});
  }catch(e){setNotice(e.message||'Could not promote the approved research signal.');}
  finally{setPromoting(null);}
 }
 if(!canRead)return null;
 const signals=(market?.signals||[]).filter(s=>signalFilter==='all'||s.source_kind===signalFilter||s.review_status===signalFilter);
 const scanHealth=market?.source_health||[];
 const latestScan=scanHealth[0];
 const drafts=market?.marketing_drafts||[];
 return <section id="ago-opportunities" className="opportunity-radar" aria-label="Company opportunity radar">
  <header><div><h3>Continuous Market & Opportunity Intelligence</h3>
    <p>Evidence from official news feeds, research papers, industrial reporting and open metadata APIs. Scoring is a relevance heuristic, not proven demand or profit. CEO-accountable nominations go to founder review.</p></div>
    {canScan&&<button type="button" onClick={scan} disabled={working}>{working?'Checking…':'Scan catalog ideas'}</button>}
  </header>
  {notice&&<p role="status">{notice}</p>}
  <div className="management-metrics">
   <span><strong>{market?.signal_total??'—'}</strong> Sourced signals stored</span>
   <span><strong>{market?.signals?.filter(s=>s.review_status==='shortlisted').length??'—'}</strong> CEO queue nominations</span>
   <span><strong>{drafts.length}</strong> Unpublished marketing drafts</span>
   <span><strong>{latestScan?dated(latestScan.checked_at):'Not checked'}</strong> Last feed scan</span>
  </div>
  {market===null?<p role="status">Internet intelligence database unavailable. Apply migration 055 and start the separate local research watcher. No live research is claimed.</p>:
   <>
   <p className="muted">Latest source: {latestScan?.source_name||'none'} · {latestScan?.outcome||'no run recorded'} · {scanHealth.filter(s=>s.outcome==='degraded').length} recent feed failures. The watcher must run independently from this web page, even when delivery tasks are active.</p>
   <button type="button" onClick={()=>setSignalsOpen(x=>!x)}>{signalsOpen?'Hide':'View'} sourced opportunities</button>
   {signalsOpen&&<div className="market-signal-list">
    <div className="market-signal-filters" role="group" aria-label="Filter internet opportunities">
     {['all','research','news','article','shortlisted'].map(key=><button type="button" key={key} aria-pressed={signalFilter===key} onClick={()=>setSignalFilter(key)}>{key}</button>)}
    </div>
    {signals.length===0?<p>No source evidence stored for this filter. Research does not fabricate results while feeds are offline.</p>:
     signals.map(s=><article className="market-signal" key={s.id}>
      <strong>{s.title}</strong>
      <small>{s.source_name} · {s.source_kind} · Source: {dated(s.published_at)} · Recorded: {dated(s.discovered_at)}</small>
      <p>{s.excerpt||'Only the headline was supplied by the source feed.'}</p>
      <small>Relevance: {s.opportunity_score}/100 · {s.score_basis} · {s.potential_customer}</small>
      <small>Status: {s.review_status} · {s.evidence_level} {s.executive_owner_name?'· Accountable CEO: '+s.executive_owner_name:''}</small>
      {s.approval_status&&<small>Founder authorization: {s.approval_status} · Does not authorize product launch, sales or spending</small>}
      {s.linked_project_id?<small>{me.roles?.includes('founder')
       ? <a href="#ago-project-portfolio">Linked governed draft project: {s.linked_project_id} ↗</a>
       : <>Linked governed draft project: {s.linked_project_id} · founder-only details</>}</small>:
       s.approval_status==='approved'&&canScan?<button type="button" disabled={Boolean(promoting)}
        onClick={()=>promote(s)}>{promoting===s.id?'Converting…':'Create governed project draft from approved research'}</button>:null}
      {safeUrl(s.source_url)&&<p><a href={safeUrl(s.source_url)} target="_blank" rel="noopener noreferrer">Open original evidence ↗</a></p>}
     </article>)}
    <p>Showing {signals.length} of {market.signal_total} unique stored signals. Source evidence needs customer validation before CEO investment decisions.</p>
   </div>}
   <h4>Promotion & social media desk</h4>
   <p>Prepared posts are visible and traceable. External publication, ad campaigns, billing and paid promotion remain disabled without account connections, reviewed content and explicit spend limits.</p>
   <button type="button" onClick={()=>setDraftsOpen(x=>!x)}>{draftsOpen?'Hide':'Inspect'} {drafts.length} drafts</button>
   {draftsOpen&&<div className="opportunity-items">
    {!drafts.length?<p>No eligible approved active projects with marketing drafts. The research worker creates draft copy only for active governed plans.</p>:
     drafts.map(d=><article key={d.id}>
       <strong>{d.project_title} · {d.platform}</strong>
       <small>Status: {d.stage} · {dated(d.created_at)}</small>
       <p>{d.draft_text}</p>
       {d.external_post_url&&safeUrl(d.external_post_url)&&<a href={safeUrl(d.external_post_url)} target="_blank" rel="noopener noreferrer">Verified external record ↗</a>}
       {me.roles?.includes('founder')&&<p><a href="#ago-project-portfolio">Inspect linked project ↓</a></p>
      </article>)}
   </div>}
   </>}
  <h4>Catalog business hypotheses (fallback when news feeds are unavailable)</h4>
  {rows===null?<p>Catalog opportunity data unavailable or migration 054 not applied.</p>:
   !rows.length?<p>No recorded catalog hypotheses. Scheduled local scanner is separate from internet research.</p>:
    <>
     <p>{rows.filter(x=>x.approval_status==='pending').length} awaiting founder review · {rows.filter(x=>x.approval_status==='approved').length} approved for planning only</p>
     <button type="button" onClick={()=>setExpanded(v=>!v)}>{expanded?'Hide':'Inspect'} catalog hypotheses</button>
     {expanded&&<div className="opportunity-items">{rows.map(o=><article key={o.id}>
      <strong>{o.title}</strong><small>Approval: {o.approval_status} · Responsible: {o.accountable_manager_name}</small>
      {o.assignment_source==='founder_escalation'&&<small>Executive staffing gap — founder escalation</small>}
      <p><b>Potential customers:</b> {o.target_customer}</p>
      <p><b>Problem hypothesis:</b> {o.customer_problem}</p>
      <p><b>Possible service:</b> {o.proposed_offer}</p>
      <p><b>Revenue idea (unverified):</b> {o.revenue_path}</p>
      <p><b>Validation:</b> {o.validation_next_step}</p>
      <p><a href="#company-approval-inbox">Review scoped founder approval ↑</a></p>
     </article>)}</div>}
    </>}
 </section>;
}
