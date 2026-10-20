"use client";
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {resource} from '@ago/sdk/session';
import {employeeStatus,companyLayout,activeRouteKeys,employeeProjects} from '@ago/sdk/company';
import {CommandBrain} from './command-brain';
const BASE='/v1/organization/company';
const time=value=>new Date(value).toLocaleString();
export function CompanyMap({api,me,data,onRefresh}) {
  const departments=resource(data,'departments')||[];
  const grouped=resource(data,'employees');
  const employees=useMemo(()=>Object.values(grouped||{}).flat(),[grouped]);
  const [channel,setChannel]=useState('global'),[messages,setMessages]=useState([]),[before,setBefore]=useState(null);
  const [tasks,setTasks]=useState(null),[selected,setSelected]=useState(null),[reply,setReply]=useState(null);
  const [centerDraft,setCenterDraft]=useState('');
  const [draft,setDraft]=useState(''),[query,setQuery]=useState(''),[error,setError]=useState(''),[sending,setSending]=useState(false);
  const [zoom,setZoom]=useState(.42),[pan,setPan]=useState({x:0,y:0}),[staffing,setStaffing]=useState(false),[department,setDepartment]=useState('');
  const [updated,setUpdated]=useState(null),[popup,setPopup]=useState(null),[loading,setLoading]=useState(false);
  const [eventData,setEventData]=useState(null),[eventQueue,setEventQueue]=useState([]);const lastEvent=useRef(null);
  const viewport=useRef(null),drag=useRef(null),previous=useRef(null),sequence=useRef(0),alive=useRef(false),retry=useRef(null),feed=useRef(null),staffKey=useRef(null);
  const layout=useMemo(()=>companyLayout(departments,employees,me.id),[departments,employees,me.id]);
  const points=new Map([['founder',{x:layout.center,y:layout.center}],...layout.nodes.map(n=>[n.key,n])]);
  const title=channel==='global'?'Global timeline':layout.nodes.find(n=>n.key===channel)?.name||'Conversation';
  const selectedEmployee=employees.find(e=>e.id===selected);
  const status=employeeStatus(selected,tasks);
  const routing=useMemo(()=>activeRouteKeys(layout,employees,tasks),[layout,employees,tasks]);
  const liveTaskCount=Array.isArray(tasks)?tasks.filter(t=>t.status==='running').length:0;
  const refreshActivity=useCallback(async()=>{
    try {const result=await api.request(BASE+'/activity');if(!alive.current)return;
      previous.current=new Map(result.map(t=>[t.id,t.status]));setTasks(result);setUpdated(new Date());
    }catch{if(alive.current){setTasks(null);setUpdated(null);}}
  },[api]);
  useEffect(()=>{alive.current=true;refreshActivity();const timer=setInterval(refreshActivity,7000);return()=>{alive.current=false;clearInterval(timer);};},[refreshActivity]);
  useEffect(()=>{
    let live=true;const version=++sequence.current;setMessages([]);setBefore(null);setReply(null);setError('');setLoading(true);
    async function fetchMessages(initial=false){try{
      const result=await api.request(BASE+'/chat?channel='+encodeURIComponent(channel));
      if(!live||version!==sequence.current)return;
      if(!Array.isArray(result.items))throw new Error('Conversation data unavailable.');
      setMessages(old=>initial?result.items:[...new Map([...old,...result.items].map(m=>[m.id,m])).values()].sort((a,b)=>a.id-b.id));
      if(initial)setBefore(result.next_before);setError('');
    }catch(e){if(live)setError(e.message);}finally{if(live)setLoading(false);}}
    fetchMessages(true);const timer=setInterval(fetchMessages,5000);
    return()=>{live=false;clearInterval(timer);};
  },[api,channel]);
  const refreshEvents=useCallback(async()=>{
    try{
      const next=await api.request(BASE+'/notifications');
      if(!alive.current)return;
      const high=next.recent?.[0]?.id||0;
      if(lastEvent.current!==null){
        const fresh=(next.recent||[]).filter(e=>e.id>lastEvent.current).reverse();
        if(fresh.length)setEventQueue(old=>[...old,...fresh].slice(-100));
      }
      lastEvent.current=Math.max(lastEvent.current||0,high);
      setEventData(next);
    }catch{if(alive.current)setEventData(null);}
  },[api]);
  useEffect(()=>{refreshEvents();const timer=setInterval(refreshEvents,7000);return()=>clearInterval(timer);},[refreshEvents]);
  useEffect(()=>{if(!popup&&eventQueue.length){setPopup(eventQueue[0]);setEventQueue(old=>old.slice(1));}},[popup,eventQueue]);
  useEffect(()=>{if(!popup)return;const timer=setTimeout(()=>setPopup(null),6500);return()=>clearTimeout(timer);},[popup]);
  function choose(key){setChannel(key);if(key.startsWith('employee:'))setSelected(key.slice(9));const node=layout.nodes.find(n=>n.key===key);if(node){setZoom(.85);setPan({x:(layout.center-node.x)*.85,y:(layout.center-node.y)*.85});}}
  function center(){setZoom(.42);setPan({x:0,y:0});}
  async function older(){const version=sequence.current;setLoading(true);try{
    const result=await api.request(BASE+'/chat?channel='+encodeURIComponent(channel)+'&before='+before);
    if(version!==sequence.current)return;
    setMessages(old=>[...new Map([...result.items,...old].map(m=>[m.id,m])).values()].sort((a,b)=>a.id-b.id));setBefore(result.next_before);
  }catch(e){setError(e.message);}finally{setLoading(false);}}
  async function send(event,central=false){event.preventDefault();const text=central?centerDraft:draft;if(!text.trim()||sending)return;
    const body={channel:central?'global':channel,body:text,reply_to:central?null:reply?.id||null};const signature=JSON.stringify(body);
    if(retry.current?.signature!==signature)retry.current={signature,key:crypto.randomUUID()};
    const version=sequence.current;setSending(true);setError('');
    try{const result=await api.request(BASE+'/chat',{method:'POST',body:{...body,operation_key:retry.current.key}});
      if(!alive.current)return;
      if(central){setCenterDraft('');choose('global');}
      if(version===sequence.current&&(!central||channel==='global')){setMessages(old=>[...new Map([...old,result].map(m=>[m.id,m])).values()].sort((a,b)=>a.id-b.id));if(!central){setDraft('');setReply(null);}requestAnimationFrame(()=>feed.current?.scrollTo({top:feed.current.scrollHeight,behavior:'smooth'}));}retry.current=null;
    }catch(e){setError(e.message);}finally{setSending(false);}}
  async function hire(event){event.preventDefault();const form=new FormData(event.currentTarget);
    const values={department_id:department,manager_id:form.get('manager')||null,name:form.get('name'),requirement:form.get('requirement')};
    const signature=JSON.stringify(values);if(staffKey.current?.signature!==signature)staffKey.current={signature,key:crypto.randomUUID()};
    setSending(true);try{await api.request(BASE+'/staffing',{method:'POST',body:{...values,operation_key:staffKey.current.key}});staffKey.current=null;setStaffing(false);await onRefresh();}
    catch(e){setError(e.message);}finally{setSending(false);}}
  return <section className="company-command" aria-label="Company map and conversations">
    <header className="company-heading"><div><p className="eyebrow">FOUNDER OPERATIONS · EVIDENCE BASED</p><h1>Company map</h1><p>Owner prompts, delegated work, review and accountable delivery.</p></div><button className="btn" disabled={!me.permissions.includes('organization:manage')} onClick={()=>{setDepartment(departments[0]?.id||'');setStaffing(true);}}>Add needed role</button></header>
    <CommandBrain tasks={tasks} notifications={eventData} employees={employees} onSelect={id=>choose('employee:'+id)}/>
    <div className="company-shell">
      <aside className="company-channels" aria-label="Conversation channels"><h2>Conversations</h2><input aria-label="Find department or employee" placeholder="Find a person or team…" value={query} onChange={e=>setQuery(e.target.value)}/>
        <button className={channel==='global'?'chosen':''} onClick={()=>choose('global')}>◉ Global timeline</button>
        {departments.map(d=>{const members=employees.filter(e=>e.department_id===d.id);if(query&&!d.name.toLowerCase().includes(query.toLowerCase())&&!members.some(e=>e.name.toLowerCase().includes(query.toLowerCase())))return null;
          function branch(e,seen=new Set()){if(seen.has(e.id))return null;const next=new Set([...seen,e.id]);return <li key={e.id}><button className={[channel==='employee:'+e.id?'chosen':'',routing.active.has(e.id)?'chat-assigned':'',employeeStatus(e.id,tasks).tone==='busy'?'chat-working':''].filter(Boolean).join(' ')} onClick={()=>choose('employee:'+e.id)}><span className={'presence '+employeeStatus(e.id,tasks).tone}/>{e.name}<span className="chat-event-count" aria-label="Recorded work events">{eventData?.by_employee?.[e.id]??0}</span></button><ul>{members.filter(x=>x.manager_id===e.id).map(x=>branch(x,next))}</ul></li>;}
          return <details key={d.id} open><summary>{d.name}</summary><button onClick={()=>choose('department:'+d.id)} className={channel==='department:'+d.id?'chosen':''}>Open {d.name} chat</button><ul>{members.filter(e=>!members.some(x=>x.id===e.manager_id)).map(e=>branch(e))}</ul></details>;})}
        <p className="channel-note">Channels are shared within your organization, including employee conversations.</p>
      </aside>
      <div className="company-canvas" ref={viewport} onPointerDown={e=>{if(e.target.closest('button,textarea,input,a,form'))return;drag.current={x:e.clientX,y:e.clientY,startX:pan.x,startY:pan.y};e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{if(drag.current)setPan({x:drag.current.startX+(e.clientX-drag.current.x),y:drag.current.startY+(e.clientY-drag.current.y)});}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onWheel={e=>{if(e.ctrlKey||e.target.closest('textarea'))return;setZoom(z=>Math.max(.08,Math.min(1.7,z-e.deltaY*.0007)));}}>
        <div className="map-controls"><button aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(1.7,z+.1))}>+</button><button aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(.08,z-.1))}>−</button><button onClick={center}>Founder</button><button onClick={()=>{setZoom(Math.min((viewport.current?.clientWidth||600)/layout.size,(viewport.current?.clientHeight||700)/layout.size)*.9);setPan({x:0,y:0});}}>Fit all</button><span>{Math.round(zoom*100)}%</span></div>
        <div className="company-world" style={{width:layout.size,height:layout.size,transform:`translate(calc(-50% + ${pan.x}px),calc(-50% + ${pan.y}px)) scale(${zoom})`}}>
          <svg width={layout.size} height={layout.size} aria-label="Reporting network; red lines show assigned work" role="img">{layout.edges.map((edge,i)=>{const a=points.get(edge.from),b=points.get(edge.to);return a&&b?<line key={i} className={routing.routes.has(edge.from+'>'+edge.to)?'edge-live':''} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>:null;})}</svg>
          <form className="map-founder" style={{left:layout.center,top:layout.center,transform:`translate(-50%,-50%) scale(${Math.max(1,Math.min(1.8,.75/zoom))})`}} onSubmit={e=>send(e,true)}><strong>♛ Founder / CEO</strong><small>{employees.find(e=>e.id===me.id)?.name||'Company centre'}</small><label htmlFor="founder-message">Talk to your company</label><textarea id="founder-message" value={centerDraft} onChange={e=>setCenterDraft(e.target.value)} maxLength={20000} placeholder="Your idea, project or question…" rows={3}/><button disabled={sending||!centerDraft.trim()} className="btn">Send to global chat</button></form>
          {layout.nodes.map(n=>{const state=employeeStatus(n.id,tasks);
             const project=employeeProjects(n.id,tasks);const eventCount=eventData?.by_employee?.[n.id]??0;
             return <button key={n.key} aria-label={n.type==='employee'?n.name+', '+state.label+', '+eventCount+' recorded updates':n.name} className={'map-node '+n.type+(channel===n.key?' active':'')+(n.type==='employee'&&state.tone==='busy'?' working':'')+(routing.active.has(n.id)?' assigned':'')} style={{left:n.x,top:n.y}} onClick={()=>choose(n.key)}>
               {n.type==='employee'&&<span className="map-count" title="Recorded work events">{eventCount}</span>}
               <strong>{n.type==='employee'&&<span className={'presence '+state.tone}/>} {n.name}</strong>
               <small>{n.type==='department'?'Department':(n.kind==='ai'?'AI employee · ':'Human member · ')+state.label}</small>
               {n.type==='employee'&&<small className="map-project">Project: {project[0]||'No linked project'}{project.length>1?' +'+(project.length-1):''}</small>}
               {n.type==='employee'&&state.tasks.find(t=>t.status==='running')&&<small className="map-task">{state.tasks.find(t=>t.status==='running').action}</small>}
               {n.type==='employee'&&<span className="node-action">View work details ↗</span>}
             </button>;})}
        </div>
        <div className="map-legend"><span><i className="presence idle"/>Idle</span><span><i className="presence busy"/>Busy</span><span><i className="presence waiting"/>Waiting</span><span><i className="presence unknown"/>Unknown</span><span className="legend-live">━ Active assignment</span><span>{liveTaskCount} running tasks</span><small>{updated?'Checked '+updated.toLocaleTimeString():'Activity unavailable'}</small></div>
        {!employees.length&&<div className="map-empty">{grouped===null?'People data unavailable. Check your permissions or refresh.':'Add a role when your project needs one. It will appear in its department.'}</div>}
        {popup&&<div className="activity-pop" role="status"><button aria-label="Dismiss update" onClick={()=>setPopup(null)}>×</button><strong>Update #{popup.id} · {employees.find(e=>e.id===popup.employee_id)?.name||'Employee'}</strong><p>{popup.body}</p><small>Saved work event · {eventQueue.length} more queued</small></div>}
      </div>
      <section className="company-chat" aria-label={title}><header><h2>{title}</h2><p>Conversation & activity · saved timeline</p></header>
        {selectedEmployee&&channel==='employee:'+selected&&<section className="employee-inspector" aria-label="Selected employee work details">
          <h3><span className={'presence '+status.tone}/>{selectedEmployee.name} <small>{status.label}</small></h3>
          <dl><dt>Type</dt><dd>{selectedEmployee.kind==='ai'?'AI role · runtime authorization separate':'Human member'}</dd>
           <dt>Department</dt><dd>{departments.find(d=>d.id===selectedEmployee.department_id)?.name||'Unknown'}</dd>
           <dt>Reports to</dt><dd>{employees.find(e=>e.id===selectedEmployee.manager_id)?.name||'Founder / department root'}</dd>
           <dt>Current projects</dt><dd>{employeeProjects(selected,tasks).join(', ')||'No project linked'}</dd>
           <dt>Recorded updates</dt><dd>{eventData?.by_employee?.[selected]??'Unavailable'}</dd>
           <dt>Core responsibility</dt><dd>Deliver assigned work and verifiable evidence within approved scope.</dd>
           <dt>Additional responsibilities</dt><dd>Maintain code, tests and documentation; report blockers, quality outcomes and completion to immediate superior. Support publishable release checks.</dd></dl>
           <h4>Assigned tasks ({status.tasks.length})</h4>{status.tasks.length?status.tasks.slice(0,12).map(t=><div key={t.id}><strong>{t.action}</strong><p>{t.status} · {t.project_name||'No linked project plan'}</p></div>):<p>{tasks===null?'Activity could not be verified.':'No assigned tasks.'}</p>}
           <h4>Latest work events</h4>{(eventData?.recent||[]).filter(e=>e.employee_id===selected).slice(0,5).map(e=><div key={e.id}><small>#{e.id} · {time(e.created_at)}</small><p>{e.body}</p></div>)}
           <p><a href="/tools/">GitHub projects, reviewed operations and delivery evidence →</a></p>
        </section>}
        <div className="company-feed" ref={feed}>{before&&<button onClick={older} disabled={loading}>Load earlier messages</button>}{loading&&<p>Loading timeline…</p>}{!loading&&!messages.length&&<p className="chat-empty">Start the conversation. Task updates will appear here as work changes.</p>}{messages.map(m=><article key={m.id} id={'chat-'+m.id} className={'chat-message '+m.kind}><header><strong>{m.author_name}</strong><time dateTime={m.created_at}>{time(m.created_at)}</time></header><small>{m.kind==='status'?'Task status · ':''}{m.channel==='global'?'Global':layout.nodes.find(n=>n.key===m.channel)?.name||'Company'}</small>{m.reply_to&&<blockquote>↳ {m.reply_author||'Reply'} #{m.reply_to}<p>{m.reply_body?.slice(0,180)||'Earlier message'}</p></blockquote>}<p>{m.body}</p><button onClick={()=>setReply(m)}>Reply</button></article>)}</div>
        <form className="company-compose" onSubmit={send}>{reply&&<div>Reply to {reply.author_name}: {reply.body.slice(0,65)} <button type="button" onClick={()=>setReply(null)}>Cancel</button></div>}<label htmlFor="company-message">Message {title}</label><textarea id="company-message" placeholder="Write your idea, question or project brief…" value={draft} maxLength={20000} rows={3} onChange={e=>setDraft(e.target.value)} required/><div><small>Unlimited conversation history · 20,000 characters/message</small><button className="btn primary" disabled={sending||!draft.trim()}>{sending?'Saving…':'Send'}</button></div><small>Sending saves a message. AI replies and task execution require a connected runtime.</small></form>
      </section>
    </div>
    <div className="command-delivery"><section><h3>Delivery accountability</h3><p>All employees own tested, documented, market-ready deliverables. No 'published' status without evidence, independent QA and required approval.</p></section><section><h3>Reporting & founder control</h3><p>Staff raise questions and module reports to their immediate manager. Founder starts projects, approves consequential steps and can interrupt or revise the scope.</p></section><section><h3>GitHub project workspace</h3><p>Use the reviewed GitHub lifecycle for commits, pull requests, documentation and CI. Live repository state must be verified per project, not assumed.</p><a href="/tools/">Open Operations & Tools →</a></section></div>
    {error&&<p role="alert" className="company-error">{error}</p>}
    {staffing&&<div className="staffing-backdrop"><section onKeyDown={e=>{if(e.key==='Escape')setStaffing(false);if(e.key==='Tab'){const controls=[...e.currentTarget.querySelectorAll('input,select,textarea,button')].filter(x=>!x.disabled);const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}}} role="dialog" aria-modal="true" aria-labelledby="staff-title" className="staffing-dialog"><h2 id="staff-title">Add a role your project needs</h2>{error&&<p role="alert">{error}</p>}<form onSubmit={hire}><label>Role name<input name="name" required maxLength={150} autoFocus placeholder="e.g. Research Scientist"/></label><label htmlFor="staff-department">Department</label><select id="staff-department" value={department} onChange={e=>setDepartment(e.target.value)} required><option value="">Choose department</option>{departments.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><label htmlFor="staff-manager">Reports to</label><select id="staff-manager" name="manager" key={department}><option value="">Department root · connected to founder</option>{employees.filter(e=>e.department_id===department).map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><label>Why is this role needed?<textarea name="requirement" minLength={10} maxLength={3000} required placeholder="Describe the project requirement and expected work."/></label><p>This creates an AI profile and records the requirement. Model access and execution permissions are configured separately.</p><button className="btn" disabled={sending||!department}>Create role</button><button type="button" className="btn" onClick={()=>setStaffing(false)}>Cancel</button></form></section></div>}
  </section>;
}
