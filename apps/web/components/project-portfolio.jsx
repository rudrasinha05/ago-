"use client";
import {useEffect,useRef,useState} from 'react';
import {RecoveryHint} from './recovery-hint';
import {canReadDelivery,deliveryPage} from './founder-delivery-state';
import {PORTFOLIO_FILTERS,portfolioCounts,portfolioRows} from './project-portfolio-state';

/** Founder portfolio: every company project on one screen with its live status. Read-only. */
export function ProjectPortfolio({api,me,active=true,refreshSignal=0,onOpen,onApproval}){
 const [rows,setRows]=useState(null),[more,setMore]=useState(false),[offset,setOffset]=useState(0);
 const [filter,setFilter]=useState('all'),[error,setError]=useState(''),[failure,setFailure]=useState(null);
 const [loading,setLoading]=useState(false),[refresh,setRefresh]=useState(0);
 const sequence=useRef(0);
 const readable=canReadDelivery(me);
 useEffect(()=>{
  if(!readable||!active){sequence.current++;return undefined;}
  let live=true;
  async function load(){
   const version=++sequence.current;setLoading(true);
   try{
    const page=deliveryPage(await api.request('/v1/organization/company/projects/delivery-overview?limit=20&offset='+offset));
    // Optional: income and commercial stage. Unavailable means "not recorded", never invented.
    const list=await api.request('/v1/organization/company/projects?limit=50&offset=0').catch(()=>null);
    if(live&&version===sequence.current){setRows(portfolioRows(page,list));setMore(page.more_projects_possible);setError('');setFailure(null);}
   }catch(e){if(live&&version===sequence.current){setRows(null);setFailure(e);setError(e.message||'Project portfolio unavailable.');}}
   finally{if(live&&version===sequence.current)setLoading(false);}
  }
  load();
  const timer=setInterval(load,20000);
  return()=>{live=false;sequence.current++;clearInterval(timer);};
 },[api,readable,active,offset,refresh,refreshSignal]);
 if(!readable)return null;
 const counts=rows?portfolioCounts(rows):null;
 const shown=rows?rows.filter(r=>filter==='all'||r.group===filter):[];
 return <section id="ago-projects-overview" className="project-portfolio-overview" aria-label="All projects" aria-busy={loading}>
  <header><div><h3>All projects</h3>
   <p>Every company project with its live status, AI team and recorded income. Open a project to see all of its details.</p></div>
   <button type="button" disabled={loading} onClick={()=>setRefresh(x=>x+1)}>Refresh</button>
  </header>
  {error&&<p role="alert">{error}</p>}{error&&<RecoveryHint error={failure}/>}
  {!rows&&!error&&<p role="status">Loading projects…</p>}
  {rows&&<div className="portfolio-filters" role="group" aria-label="Filter projects">
   {PORTFOLIO_FILTERS.map(([key,label])=><button key={key} type="button" aria-pressed={filter===key}
    onClick={()=>setFilter(key)}>{label} <b>{counts[key]}</b></button>)}
  </div>}
  {rows&&!rows.length&&<p>No projects yet. Start one with a project brief below.</p>}
  {rows&&rows.length>0&&!shown.length&&<p>No project matches this filter.</p>}
  {shown.length>0&&<ul className="portfolio-list">{shown.map(r=><li key={r.id} className={'portfolio-row group-'+r.group}>
   <div className="portfolio-main">
    <strong>{r.title}</strong>
    <span className={'delivery-state state-'+r.state}>{r.status}</span>
   </div>
   <div className="portfolio-facts">
    <span><b>Progress:</b> {r.reviewed}/{r.stageCount} stages passed QA{r.running?' · '+r.running+' running':''}{r.failed?' · '+r.failed+' failed':''}</span>
    <span><b>AI team:</b> {r.team.length?r.team.join(', '):'Not staffed yet'}</span>
    <span><b>Income:</b> {r.income.label} · {r.commercial}</span>
    {r.released&&<span><b>Release:</b> verified release-ready</span>}
   </div>
   <div className="delivery-actions">
    <button type="button" onClick={()=>onOpen?.(r.project)} aria-label={'Open project details: '+r.title}>Open project</button>
    {r.decisions>0&&onApproval&&<button type="button" onClick={()=>onApproval(r.project.pending_approvals.find(a=>a.requires_founder_decision===true).approval_id)}
     aria-label={'Review '+r.decisions+' decision(s) for '+r.title}>{r.decisions} decision{r.decisions>1?'s':''} for you</button>}
   </div>
  </li>)}</ul>}
  {(offset>0||more)&&<nav className="delivery-actions" aria-label="Project portfolio pages">
   <button type="button" disabled={offset===0||loading} onClick={()=>setOffset(x=>Math.max(0,x-20))}>Previous projects</button>
   <span>Page {offset/20+1}</span>
   <button type="button" disabled={!more||loading} onClick={()=>setOffset(x=>x+20)}>Next projects</button>
  </nav>}
  <small>Status comes from recorded AGO evidence. A project is not complete or released unless AGO verified it.</small>
 </section>;
}
