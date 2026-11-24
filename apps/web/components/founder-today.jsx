"use client";
import {useEffect,useMemo,useRef,useState} from 'react';
import {canReadDelivery,deliveryPage} from './founder-delivery-state';
import {headline,needsYou,projectLine} from './founder-today-state';
import {boardMembers} from './board-codenames';
import {StageRecovery} from './stage-recovery';
import {BoardRoom} from './board-room';

const SPEAK_ICON=<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/></svg>;

/** Founder's first glance: what is happening, what needs me, who to ask.
 * Everything comes from recorded server data; details stay in the other tabs. */
export function FounderToday({api,me,tasks,board,employees,active=true,refreshSignal=0,talkRequest=null,onApproval,onProject,onRunProject,onSection}){
 const [page,setPage]=useState(null),[error,setError]=useState(''),[refresh,setRefresh]=useState(0),[notice,setNotice]=useState('');
 const [seat,setSeat]=useState('Strategy & Vision');
 const room=useRef(null);
 const readable=canReadDelivery(me);
 useEffect(()=>{if(talkRequest?.seat)setSeat(talkRequest.seat);},[talkRequest]);
 useEffect(()=>{
  if(!readable||!active)return undefined;
  let live=true;
  async function load(){
   try{const result=deliveryPage(await api.request('/v1/organization/company/projects/delivery-overview?limit=20&offset=0'));
    if(live){setPage(result);setError('');}}
   catch(e){if(live)setError(e?.message||'Project status is unavailable right now.');}
  }
  load();const timer=setInterval(load,15000);
  return()=>{live=false;clearInterval(timer);};
 },[api,readable,active,refresh,refreshSignal]);
 const projects=useMemo(()=>page?.projects||[],[page]);
 const needs=useMemo(()=>needsYou(projects,me.id),[projects,me.id]);
 const lines=useMemo(()=>projects.map(p=>({...projectLine(p,me.id),record:p})),[projects,me.id]);
 const running=Array.isArray(tasks)?tasks.filter(t=>t.status==='running').length:0;
 const members=useMemo(()=>boardMembers(board,employees),[board,employees]);
 function talk(seatName){setSeat(seatName);requestAnimationFrame(()=>{room.current?.scrollIntoView({block:'start',behavior:'auto'});document.getElementById('board-room-input')?.focus();});}
 // The tab panel is already the "Today" region: this is plain content inside it.
 if(!readable)return <div className="founder-today"><h2>Today</h2>
  <p>This summary is for the Founder. Your work is in Execution &amp; Delivery and Organization &amp; Chat.</p></div>;
 return <div className="founder-today">
  <header className="today-hero">
   <div>
    <p className="today-date">{new Date().toLocaleDateString(undefined,{weekday:'long',day:'numeric',month:'long'})}</p>
    <h2>{page?headline({projects,needs,running}):error?'Project status is unavailable.':'Reading your company…'}</h2>
   </div>
   <button type="button" className="today-ask" onClick={()=>talk(seat)}>{SPEAK_ICON}Ask the Board</button>
  </header>
  {error&&<p role="alert" className="today-error">{error} <button type="button" onClick={()=>setRefresh(x=>x+1)}>Try again</button></p>}
  {notice&&<p role="status" className="today-notice">{notice}</p>}

  <div className="today-stats" role="list" aria-label="At a glance">
   <div role="listitem"><b>{page?lines.filter(l=>!l.done).length:'–'}</b><span>active projects</span></div>
   <div role="listitem" className={needs.length?'attention':undefined}><b>{page?needs.length:'–'}</b><span>need you</span></div>
   <div role="listitem"><b>{Array.isArray(tasks)?running:'–'}</b><span>AI tasks running</span></div>
   <div role="listitem"><b>{page?lines.reduce((n,l)=>n+l.passed,0):'–'}</b><span>stages passed QA</span></div>
  </div>

  <section className="today-needs" aria-labelledby="today-needs-title">
   <h3 id="today-needs-title">Needs you</h3>
   {page&&!needs.length&&<p className="today-calm">Nothing waits for you. The AI team carries on, and anything stuck goes up to the AI CEO first.</p>}
   <ul>{needs.map(item=><li key={item.key} className={'today-need '+item.kind}>
    <div><strong>{item.title}</strong><p>{item.kind==='decision'?'Your decision: '+item.detail:item.detail}</p></div>
    <div className="today-need-actions">
     {item.kind==='decision'&&<button type="button" onClick={()=>onApproval(item.approval_id)} aria-label={'Review and decide: '+item.title+' for '+item.detail}>Review &amp; decide</button>}
     {item.kind==='hold'&&item.rework&&<StageRecovery api={api} project={item.project} stage={item.stage} onRecovered={r=>{
      setNotice('Rework task created for '+r.stage+'. Next: press "Run the project" so the AI team picks it up.');setRefresh(x=>x+1);}}/>}
     {item.kind==='hold'&&<button type="button" onClick={()=>onProject(item.project)}>Open project</button>}
    </div>
   </li>)}</ul>
  </section>

  <section className="today-projects" aria-labelledby="today-projects-title">
   <div className="today-section-head"><h3 id="today-projects-title">Projects</h3>
    <button type="button" onClick={()=>onSection('ago-tab-projects')}>Start a project</button></div>
   {page&&!lines.length&&<p className="today-calm">No project yet. Start one from a short brief.</p>}
   <ul>{lines.map(line=><li key={line.project_id} className="today-line" aria-label={'Project '+line.title}>
    <div className="today-line-head">
     <strong>{line.title}</strong>
     <span>{line.total?line.passed+' of '+line.total+' stages passed':'No stages'}{line.manager?' · '+line.manager:''}</span>
    </div>
    <ol className="today-track" aria-label={'Stages of '+line.title}>
     {line.stations.map(s=><li key={s.stage} className={'station '+s.state+(s.stage===line.current?' current':'')}>
      <i aria-hidden="true"/><b>{s.name}</b><small>{s.label}</small>
     </li>)}
    </ol>
    <p className="today-now">{line.now}</p>
    <div className="today-line-actions">
     {!line.done&&line.record.plan_status==='active'&&<button type="button" onClick={()=>onRunProject(line.record)}>Run the project</button>}
     <button type="button" onClick={()=>onProject(line.record)}>Details &amp; evidence</button>
    </div>
   </li>)}</ul>
  </section>

  <section className="today-board" aria-labelledby="today-board-title">
   <div className="today-section-head"><h3 id="today-board-title">Your Board</h3>
    <button type="button" onClick={()=>onSection('ago-tab-board')}>Board &amp; Roles</button></div>
   <ul>{members.map(m=><li key={m.seat} className={'board-card'+(m.member?'':' vacant')} style={{'--seat':m.color}}>
    <span className="board-badge" aria-hidden="true">{m.initials}</span>
    <div><strong>{m.codename}</strong><small>{m.role} · {m.member?m.member.name:'Vacant seat'}</small><p>{m.duty}</p></div>
    <button type="button" disabled={!m.member} onClick={()=>talk(m.seat)} aria-label={'Talk to '+m.codename}>{SPEAK_ICON}Talk</button>
   </li>)}</ul>
  </section>
  <div ref={room}><BoardRoom api={api} me={me} members={members} seat={seat} onSeat={setSeat}/></div>
 </div>;
}
