"use client";
import Link from 'next/link';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {resource} from '@ago/sdk/session';
import {employeeStatus,companyLayout,activeRouteKeys,employeeProjects} from '@ago/sdk/company';
import {CommandBrain} from './command-brain';
import {RoleEditor,UpwardReports} from './company-governance';
import {FounderProjectIntake} from './founder-project-intake';
import {CompanyApprovals} from './company-approvals';
import {ManagementWorkload} from './company-management';
import {OpportunityRadar} from './company-opportunities';
const BASE='/v1/organization/company';
const time=value=>new Date(value).toLocaleString();
export function CompanyMap({api,me,data,onRefresh}) {
  const departments=resource(data,'departments')||[];
  const grouped=resource(data,'employees');
  const employees=useMemo(()=>Object.values(grouped||{}).flat(),[grouped]);
  const founderView=me.roles?.includes('founder');
  const ownMember=employees.find(e=>e.id===me.id);
  const canReadChannel=key=>{
    if(founderView||key==='global')return true;
    if(key.startsWith('department:'))return ownMember?.department_id===key.slice(11);
    if(key.startsWith('employee:')){
      const person=employees.find(e=>e.id===key.slice(9));
      return key.slice(9)===me.id||person?.manager_id===me.id;
    }
    return false;
  };
  const [approvalRefresh,setApprovalRefresh]=useState(0);
  const [approvalList,setApprovalList]=useState(null);
  const receiveApprovalData=useCallback(items=>setApprovalList(items),[]);
  const [channel,setChannel]=useState('global'),[messages,setMessages]=useState([]),[before,setBefore]=useState(null);
  const [tasks,setTasks]=useState(null),[selected,setSelected]=useState(null),[reply,setReply]=useState(null);
  const [portfolioMap,setPortfolioMap]=useState([]);
  const [centerDraft,setCenterDraft]=useState('');
  const [draft,setDraft]=useState(''),[query,setQuery]=useState(''),[error,setError]=useState(''),[sending,setSending]=useState(false);
  const [zoom,setZoom]=useState(.42),[pan,setPan]=useState({x:0,y:0}),[staffing,setStaffing]=useState(false),[department,setDepartment]=useState('');
  const [fullscreen,setFullscreen]=useState(false),[inspectorOpen,setInspectorOpen]=useState(true);
  const [addingDepartment,setAddingDepartment]=useState(false);
  const [updated,setUpdated]=useState(null),[popup,setPopup]=useState(null),[loading,setLoading]=useState(false);
  const [eventData,setEventData]=useState(null),[eventQueue,setEventQueue]=useState([]);const [githubState,setGithubState]=useState(null),[governanceData,setGovernanceData]=useState(null);const lastEvent=useRef(null);
  const viewport=useRef(null),drag=useRef(null),previous=useRef(null),sequence=useRef(0),alive=useRef(false),retry=useRef(null),feed=useRef(null),staffKey=useRef(null);
  const layout=useMemo(()=>companyLayout(departments,employees,me.id),[departments,employees,me.id]);
  const points=new Map([['founder',{x:layout.center,y:layout.center}],...layout.nodes.map(n=>[n.key,n])]);
  const title=channel==='global'?'Global timeline':layout.nodes.find(n=>n.key===channel)?.name||'Conversation';
  const selectedEmployee=employees.find(e=>e.id===selected);
  const status=employeeStatus(selected,tasks);
  const assignedRepos=id=>(githubState||[]).filter(p=>p.pm_id===id||p.qa_id===id||p.developer_ids.includes(id)).map(p=>p.repository);
  const displayProjects=id=>[...new Set([
    ...employeeProjects(id,tasks),...assignedRepos(id),
    ...portfolioMap.filter(p=>p.accountable_manager_id===id).map(p=>p.title+' (delivery owner)'),
    ...portfolioMap.flatMap(p=>(p.stages||[]).filter(stage=>stage.suggested_assignee_id===id)
      .map(stage=>p.title+' ('+stage.stage+' proposed)')),
  ])];
  const routing=useMemo(()=>activeRouteKeys(layout,employees,tasks),[layout,employees,tasks]);
  const liveTaskCount=Array.isArray(tasks)?tasks.filter(t=>t.status==='running').length:0;
  // Keep each reply directly below its recorded parent when that parent is visible.
  // Messages whose parent is on an older page stay visible as standalone replies.
  const threads=useMemo(()=>{
    const ids=new Set(messages.map(m=>m.id)),children=new Map();
    for(const m of messages)if(m.reply_to&&m.reply_to!==m.id&&ids.has(m.reply_to)){
      if(!children.has(m.reply_to))children.set(m.reply_to,[]);
      children.get(m.reply_to).push(m);
    }
    return {children,roots:messages.filter(m=>!m.reply_to||!ids.has(m.reply_to)||m.reply_to===m.id)};
  },[messages]);
  useEffect(()=>{
    if(!fullscreen)return;
    const prior=document.body.style.overflow;
    document.body.style.overflow='hidden';
    const onKey=e=>{if(e.key==='Escape')setFullscreen(false);};
    document.addEventListener('keydown',onKey);
    return()=>{document.body.style.overflow=prior;document.removeEventListener('keydown',onKey);};
  },[fullscreen]);
  const refreshActivity=useCallback(async()=>{
    try {const result=await api.request(BASE+'/activity');if(!alive.current)return;
      previous.current=new Map(result.map(t=>[t.id,t.status]));setTasks(result);setUpdated(new Date());
    }catch{if(alive.current){setTasks(null);setUpdated(null);}}
  },[api]);
  useEffect(()=>{alive.current=true;refreshActivity();const timer=setInterval(refreshActivity,7000);return()=>{alive.current=false;clearInterval(timer);};},[refreshActivity]);
  useEffect(()=>{
    if(!me.permissions.includes('organization:read')||!me.permissions.includes('brain:read'))return;
    let live=true;
    async function loadPortfolio(){
      try{
        const all=[];
        for(let offset=0;offset<300;offset+=100){
          const page=await api.request(BASE+'/projects?limit=100&offset='+offset);
          if(!Array.isArray(page))break;
          all.push(...page);
          if(page.length<100)break;
        }
        if(live)setPortfolioMap(all);
      }catch{if(live)setPortfolioMap([]);}
    }
    loadPortfolio();
    const timer=setInterval(loadPortfolio,60000);
    return()=>{live=false;clearInterval(timer);};
  },[api,me.permissions]);

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
  const refreshGovernance=useCallback(async()=>{
    try {const result=await api.request(BASE+'/governance');if(alive.current)setGovernanceData(result);}
    catch {if(alive.current)setGovernanceData(null);}
  },[api]);
  useEffect(()=>{refreshGovernance();},[refreshGovernance]);
  async function appointBoard(seat,employeeId){
    setError('');
    try {await api.request(BASE+'/board/appoint',{method:'POST',body:{seat,employee_id:employeeId}});await refreshGovernance();}
    catch(e){setError(e.message);}
  }
  const refreshGitHub=useCallback(async()=>{
    try{
      const catalog=await api.request('/v1/platform/catalog');
      if(!alive.current)return;
      const projects=(catalog.github_projects||[]).slice(0,12);
      const checked=await Promise.all(projects.map(async p=>{
        const item=p.payload||p;let status=null;
        try{status=await api.request('/v1/platform/github/projects/'+encodeURIComponent(item.id)+'/status');}
        catch{status=null;}
        return {id:item.id,repository:item.repository,pm_id:item.pm_id,qa_id:item.qa_id,developer_ids:item.developer_ids||[],status};
      }));
      if(alive.current)setGithubState(checked);
    }catch{if(alive.current)setGithubState(null);}
  },[api]);
  useEffect(()=>{refreshGitHub();const timer=setInterval(refreshGitHub,45000);return()=>clearInterval(timer);},[refreshGitHub]);
  useEffect(()=>{if(!popup&&eventQueue.length){setPopup(eventQueue[0]);setEventQueue(old=>old.slice(1));}},[popup,eventQueue]);
  useEffect(()=>{if(!popup)return;const timer=setTimeout(()=>setPopup(null),6500);return()=>clearTimeout(timer);},[popup]);
  function choose(key){if(!canReadChannel(key)){setError('This AGO conversation is private to its authorized participants.');return;}setChannel(key);setReply(null);setInspectorOpen(true);if(key.startsWith('employee:'))setSelected(key.slice(9));const node=layout.nodes.find(n=>n.key===key);if(node){setZoom(.85);setPan({x:(layout.center-node.x)*.85,y:(layout.center-node.y)*.85});}}
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
  function renderMessage(m,depth=0){
    const children=threads.children.get(m.id)||[];
    return <article key={m.id} id={'chat-'+m.id} data-reply-to={m.reply_to||undefined}
      className={'chat-message '+m.kind+(depth?' chat-thread-reply':'')} style={{'--thread-depth':Math.min(depth,5)}}>
      <header><strong>{m.author_name}</strong><time dateTime={m.created_at}>{time(m.created_at)}</time></header>
      <small>{m.kind==='status'?'Task status · ':''}{m.channel==='global'?'Global':layout.nodes.find(n=>n.key===m.channel)?.name||'Company'}</small>
      {m.reply_to&&<div className="chat-reply-context">↳ Reply to {m.reply_author||'message #'+m.reply_to}{!depth&&<span> · {m.reply_body?.slice(0,140)||'Older message'}</span>}</div>}
      <p>{m.body}</p>
      <div className="chat-message-actions"><button type="button" onClick={()=>{setReply(m);document.getElementById('company-message')?.focus();}}>Reply</button>
       {children.length>0&&<small>{children.length} {children.length===1?'reply':'replies'}</small>}</div>
      {children.length>0&&<div className="chat-thread-children">{children.map(child=>renderMessage(child,depth+1))}</div>}
    </article>;
  }
  async function hire(event){event.preventDefault();const form=new FormData(event.currentTarget);
    const values={department_id:department,manager_id:form.get('manager')||null,name:form.get('name'),requirement:form.get('requirement')};
    const signature=JSON.stringify(values);if(staffKey.current?.signature!==signature)staffKey.current={signature,key:crypto.randomUUID()};
    setSending(true);try{await api.request(BASE+'/staffing',{method:'POST',body:{...values,operation_key:staffKey.current.key}});staffKey.current=null;setStaffing(false);await onRefresh();}
    catch(e){setError(e.message);}finally{setSending(false);}}
  async function createDepartment(event){
    event.preventDefault();
    const name=String(new FormData(event.currentTarget).get('name')||'').trim();
    if(!name||sending)return;
    setSending(true);setError('');
    try{
      await api.request('/v1/organization/departments',{method:'POST',body:{name}});
      setAddingDepartment(false);
      await onRefresh();
    }catch(e){setError(e.message);}finally{setSending(false);}
  }
  return <section id="ago-unified-cockpit" className="company-command" aria-label="Company map and conversations">
    <header className="company-heading"><div><p className="eyebrow">FOUNDER OPERATIONS · EVIDENCE BASED</p><h1>Company map</h1><p>Owner prompts, delegated work, review and accountable delivery.</p></div>{me.permissions.includes('organization:manage')&&<div className="company-heading-actions"><button type="button" className="btn" aria-expanded={addingDepartment} onClick={()=>setAddingDepartment(v=>!v)}>Add department</button><button type="button" className="btn" disabled={!departments.length} onClick={()=>{setDepartment(departments[0]?.id||'');setStaffing(true);}}>Add needed role</button></div>}</header>
    {addingDepartment&&me.permissions.includes('organization:manage')&&<form className="company-add-department" onSubmit={createDepartment}><label htmlFor="company-department-name">Department name</label><input id="company-department-name" name="name" autoFocus required maxLength={150} placeholder="e.g. Engineering"/><button className="btn" disabled={sending}>{sending?'Saving…':'Create department'}</button><button type="button" className="btn" onClick={()=>setAddingDepartment(false)}>Cancel</button></form>}
    <nav className="company-cockpit-nav" aria-label="Company control center sections">
      <a href="#ago-unified-cockpit">Company Brain</a>
      <a href="#company-approval-inbox">Founder Approvals</a>
      {me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read')&&<a href="#ago-opportunities">Business Opportunities</a>}
      {founderView&&me.permissions?.includes('brain:manage')&&<a href="#ago-project-portfolio">Project Portfolio</a>}
      {me.permissions?.includes('task:read')&&<a href="#ago-workforce">Workforce</a>}
      <a href="#ago-company-org-map">Organization & Chat</a>
    </nav>
    <CommandBrain tasks={tasks} notifications={eventData} employees={employees} governance={governanceData} canGovern={me.roles.includes('founder')} onAppoint={appointBoard} onSelect={id=>choose('employee:'+id)}/>
    <CompanyApprovals api={api} me={me} employees={employees} onData={receiveApprovalData} refreshSignal={approvalRefresh} onReviewed={refreshEvents}/>
    <FounderProjectIntake api={api} me={me} onChanged={()=>setApprovalRefresh(v=>v+1)}/>
    <ManagementWorkload api={api} me={me} refreshSignal={approvalRefresh}/>
    <OpportunityRadar api={api} me={me} onChanged={()=>setApprovalRefresh(x=>x+1)}/>
    <div id="ago-company-org-map" className={"company-shell"+(fullscreen?" company-fullscreen":"")} aria-label="Organization map workspace">
      <aside className="company-channels" aria-label="Conversation channels"><h2>Conversations</h2><input aria-label="Find department or employee" placeholder="Find a person or team…" value={query} onChange={e=>setQuery(e.target.value)}/>
        <button className={channel==='global'?'chosen':''} onClick={()=>choose('global')}>◉ Global timeline</button>
        {departments.map(d=>{const members=employees.filter(e=>e.department_id===d.id);if(query&&!d.name.toLowerCase().includes(query.toLowerCase())&&!members.some(e=>e.name.toLowerCase().includes(query.toLowerCase())))return null;
          function branch(e,seen=new Set()){if(seen.has(e.id))return null;const next=new Set([...seen,e.id]);return <li key={e.id}><button aria-label={e.name} className={[channel==='employee:'+e.id?'chosen':'',routing.active.has(e.id)?'chat-assigned':'',employeeStatus(e.id,tasks).tone==='busy'?'chat-working':''].filter(Boolean).join(' ')} onClick={()=>choose('employee:'+e.id)}><span className={'presence '+employeeStatus(e.id,tasks).tone}/>{e.name}{(eventData?.by_employee?.[e.id]??0)>0&&<span className="chat-event-count" aria-label={(eventData?.by_employee?.[e.id]??0)+" recorded work events"}>{eventData.by_employee[e.id]}</span>}</button><ul>{members.filter(x=>x.manager_id===e.id).map(x=>branch(x,next))}</ul></li>;}
          if(!canReadChannel('department:'+d.id))return null;
          return <details key={d.id} open><summary>{d.name}</summary><button onClick={()=>choose('department:'+d.id)} className={channel==='department:'+d.id?'chosen':''}>Open {d.name} chat</button><ul>{members.filter(e=>!members.some(x=>x.id===e.manager_id)).map(e=>branch(e))}</ul></details>;})}
        <p className="channel-note">Global chat is shared. Department and employee conversations are restricted to the founder and authorized members. AGO enforces access on every read and write.</p>
      </aside>
      <div className="company-canvas" ref={viewport} onPointerDown={e=>{if(e.target.closest('button,textarea,input,a,form'))return;drag.current={x:e.clientX,y:e.clientY,startX:pan.x,startY:pan.y};e.currentTarget.setPointerCapture(e.pointerId);}} onPointerMove={e=>{if(drag.current)setPan({x:drag.current.startX+(e.clientX-drag.current.x),y:drag.current.startY+(e.clientY-drag.current.y)});}} onPointerUp={()=>{drag.current=null;}} onPointerCancel={()=>{drag.current=null;}} onWheel={e=>{if(e.ctrlKey||e.target.closest('textarea'))return;setZoom(z=>Math.max(.08,Math.min(1.7,z-e.deltaY*.0007)));}}>
        <div className="map-controls"><button aria-label="Zoom in" onClick={()=>setZoom(z=>Math.min(1.7,z+.1))}>+</button><button aria-label="Zoom out" onClick={()=>setZoom(z=>Math.max(.08,z-.1))}>−</button><button onClick={center}>Founder</button><button aria-label={fullscreen?"Exit full screen":"Full screen map"} aria-pressed={fullscreen} onClick={()=>setFullscreen(v=>!v)}>{fullscreen?"Exit full screen":"⛶ Full screen"}</button><button onClick={()=>{setZoom(Math.min((viewport.current?.clientWidth||600)/layout.size,(viewport.current?.clientHeight||700)/layout.size)*.9);setPan({x:0,y:0});}}>Fit all</button><span>{Math.round(zoom*100)}%</span></div>
        <div className="company-world" style={{width:layout.size,height:layout.size,transform:`translate(calc(-50% + ${pan.x}px),calc(-50% + ${pan.y}px)) scale(${zoom})`}}>
          <svg width={layout.size} height={layout.size} aria-label="Reporting network; red lines show assigned work" role="img">{layout.edges.map((edge,i)=>{const a=points.get(edge.from),b=points.get(edge.to);return a&&b?<line key={i} className={routing.routes.has(edge.from+'>'+edge.to)?'edge-live':''} x1={a.x} y1={a.y} x2={b.x} y2={b.y}/>:null;})}</svg>
          <form className="map-founder" style={{left:layout.center,top:layout.center,transform:`translate(-50%,-50%) scale(${Math.max(1,Math.min(1.8,.75/zoom))})`}} onSubmit={e=>send(e,true)}><strong>♛ Founder · Human authority</strong><small>{employees.find(e=>e.id===me.id)?.name||'Company centre'}</small><label htmlFor="founder-message">Talk to your company</label><textarea id="founder-message" value={centerDraft} onChange={e=>setCenterDraft(e.target.value)} maxLength={20000} placeholder="Your idea, project or question…" rows={3}/><button disabled={sending||!centerDraft.trim()} className="btn">Send to global chat</button></form>
          {layout.nodes.map(n=>{const state=employeeStatus(n.id,tasks);
             const project=displayProjects(n.id);const eventCount=eventData?.by_employee?.[n.id]??0;
             const recordedRole=governanceData?.employees?.find(e=>e.id===n.id)?.role_title;
             const approvalCount=(approvalList||[]).filter(a=>a.requester_id===n.id&&a.status==='pending').length;
             return <button key={n.key} aria-label={n.type==='employee'?n.name+', '+state.label+', '+eventCount+' recorded updates':n.name} className={'map-node '+n.type+(channel===n.key?' active':'')+(n.type==='employee'&&state.tone==='busy'?' working':'')+(routing.active.has(n.id)?' assigned':'')} style={{left:n.x,top:n.y}} onClick={()=>choose(n.key)}>
               {n.type==='employee'&&eventCount>0&&<span className="map-count" title="Recorded work events">{eventCount}</span>}
               <strong>{n.type==='employee'&&<span className={'presence '+state.tone}/>} {n.name}</strong>
               <small>{n.type==='department'?'Department':(n.kind==='ai'?'AI employee · ':'Human member · ')+state.label}</small>
               {n.type==='employee'&&<small className="map-role">Role: {recordedRole||'Not assigned'}</small>}
               {n.type==='employee'&&approvalCount>0&&<small className="map-role">{approvalCount} pending approval request(s)</small>}
               {n.type==='employee'&&<small className="map-project">Project: {project[0]||'No linked project'}{project.length>1?' +'+(project.length-1):''}</small>}
               {n.type==='employee'&&state.tasks.find(t=>t.status==='running')&&<small className="map-task">{state.tasks.find(t=>t.status==='running').action}</small>}
               {n.type==='employee'&&<span className="node-action">View work details ↗</span>}
             </button>;})}
        </div>
        <div className="map-legend"><span><i className="presence idle"/>Idle</span><span><i className="presence busy"/>Busy</span><span><i className="presence waiting"/>Waiting</span><span><i className="presence unknown"/>Unknown</span><span className="legend-live">━ Active assignment</span>{liveTaskCount>0&&<span>{liveTaskCount} running tasks</span>}<small>{updated?'Checked '+updated.toLocaleTimeString():'Activity unavailable'}</small></div>
        {!employees.length&&<div className="map-empty">{grouped===null?'People data unavailable. Check your permissions or refresh.':'Add a role when your project needs one. It will appear in its department.'}</div>}
        {popup&&<div className="activity-pop" role="status"><button aria-label="Dismiss update" onClick={()=>setPopup(null)}>×</button><strong>Update #{popup.id} · {employees.find(e=>e.id===popup.employee_id)?.name||'Employee'}</strong><p>{popup.body}</p><small>Saved work event · {eventQueue.length} more queued</small></div>}
      </div>
      <section className="company-chat" aria-label={title}><header><div><h2>{title}</h2><p>Conversation & activity · saved timeline</p></div>
          {selectedEmployee&&channel==='employee:'+selected&&<button type="button" className="inspector-toggle" aria-expanded={inspectorOpen} onClick={()=>setInspectorOpen(v=>!v)}>{inspectorOpen?'Hide profile':'Show profile'}</button>}
        </header>
        {inspectorOpen&&selectedEmployee&&channel==='employee:'+selected&&<section className="employee-inspector" aria-label="Selected employee work details">
          <h3><span className={'presence '+status.tone}/>{selectedEmployee.name} <small>{status.label}</small></h3>
          <dl><dt>Type</dt><dd>{selectedEmployee.kind==='ai'?'AI role · runtime authorization separate':'Human member'}</dd>
           <dt>Department</dt><dd>{departments.find(d=>d.id===selectedEmployee.department_id)?.name||'Unknown'}</dd>
           <dt>Reports to</dt><dd>{employees.find(e=>e.id===selectedEmployee.manager_id)?.name||'Founder / department root'}</dd>
           <dt>Current projects</dt><dd>{displayProjects(selected).join(', ')||'No project linked'}</dd>
           <dt>Recorded updates</dt><dd>{eventData?.by_employee?.[selected]??'Unavailable'}</dd>
           <dt>Core responsibility</dt><dd>Deliver assigned work and verifiable evidence within approved scope.</dd>
           <dt>Additional responsibilities</dt><dd>Maintain code, tests and documentation; report blockers, quality outcomes and completion to immediate superior. Support publishable release checks.</dd></dl>
           <RoleEditor key={selected} employee={selectedEmployee} profile={governanceData?.employees?.find(e=>e.id===selected)} api={api} canManage={me.roles.includes('founder')} onSaved={refreshGovernance}/>
           <h4>Approvals</h4>
           {approvalList===null?<p>Approval history unavailable.</p>:
             !approvalList.filter(a=>a.requester_id===selected||a.task_assignee_id===selected).length?
             <p>No recorded approval requests for this employee.</p>:
             approvalList.filter(a=>a.requester_id===selected||a.task_assignee_id===selected).slice(0,5)
             .map(a=><p key={a.id}>{a.approval_type?.replaceAll('_',' ')} — {a.status} · {a.plan_title||a.task_action||a.action}</p>)}
           <p><a href="#company-approval-inbox">Open Approval Inbox for the full request and decision details ↑</a></p>
           <h4>Assigned tasks {status.tasks.length>0&&'('+status.tasks.length+')'}</h4>{status.tasks.length?status.tasks.slice(0,12).map(t=><div key={t.id}><strong>{t.action}</strong><p>{t.status} · {t.project_name||'No linked project plan'}</p></div>):<p>{tasks===null?'Activity could not be verified.':'No assigned tasks.'}</p>}
           <h4>Latest work events</h4>{(eventData?.recent||[]).filter(e=>e.employee_id===selected).slice(0,5).map(e=><div key={e.id}><small>#{e.id} · {time(e.created_at)}</small><p>{e.body}</p></div>)}
           <p><Link href="/tools/">GitHub projects, reviewed operations and delivery evidence →</Link></p>
        </section>}
        <div className="company-feed" ref={feed}>{before&&<button onClick={older} disabled={loading}>Load earlier messages</button>}{loading&&<p>Loading timeline…</p>}{!loading&&!messages.length&&<p className="chat-empty">Start the conversation. Task updates will appear here as work changes.</p>}{threads.roots.map(m=>renderMessage(m))}</div>
        <form className="company-compose" onSubmit={send}>{reply&&<div className="replying-banner"><span>↳ Replying to <strong>{reply.author_name}</strong>: {reply.body.slice(0,65)}</span> <button type="button" onClick={()=>setReply(null)}>Cancel reply</button></div>}<label htmlFor="company-message">Message {title}</label><textarea id="company-message" placeholder="Write your idea, question or project brief…" value={draft} maxLength={20000} rows={3} onChange={e=>setDraft(e.target.value)} required/><div><small>Unlimited conversation history · 20,000 characters/message</small><button className="btn primary" disabled={sending||!draft.trim()}>{sending?'Saving…':'Send'}</button></div><small>Sending saves a message. AI replies and task execution require a connected runtime.</small></form>
      </section>
    </div>
    <UpwardReports api={api} me={me} employees={employees} onRecorded={refreshEvents}/>
    <div className="command-delivery"><section><h3>Delivery accountability</h3><p>All employees own tested, documented, market-ready deliverables. No 'published' status without evidence, independent QA and required approval.</p></section><section><h3>Reporting & founder control</h3><p>Staff raise questions and module reports to their immediate manager. Founder starts projects, approves consequential steps and can interrupt or revise the scope.</p></section><section><h3>GitHub project workspace</h3>
      {githubState===null?<p>Project status unavailable or access denied. Configure approved GitHub access under Operations & Tools.</p>:!githubState.length?<p>No approved GitHub project currently linked. Connect a reviewed project before claiming code is synced.</p>:
        <ul className="github-live-list">{githubState.map(p=><li key={p.id}><strong>{p.repository}</strong><small>{p.status?(p.status.status||p.status.state||'Status checked'):'Live status unavailable'}</small></li>)}</ul>}
      <p>Commits, PRs, documentation and CI still require evidence and approval. Repository changes are never inferred from dashboard animations.</p><Link href="/tools/">View GitHub operations and CI →</Link></section></div>
    {error&&<p role="alert" className="company-error">{error}</p>}
    {staffing&&<div className="staffing-backdrop"><section onKeyDown={e=>{if(e.key==='Escape')setStaffing(false);if(e.key==='Tab'){const controls=[...e.currentTarget.querySelectorAll('input,select,textarea,button')].filter(x=>!x.disabled);const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}}} role="dialog" aria-modal="true" aria-labelledby="staff-title" className="staffing-dialog"><h2 id="staff-title">Add a role your project needs</h2>{error&&<p role="alert">{error}</p>}<form onSubmit={hire}><label>Role name<input name="name" required maxLength={150} autoFocus placeholder="e.g. Research Scientist"/></label><label htmlFor="staff-department">Department</label><select id="staff-department" value={department} onChange={e=>setDepartment(e.target.value)} required><option value="">Choose department</option>{departments.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><label htmlFor="staff-manager">Reports to</label><select id="staff-manager" name="manager" key={department}><option value="">Department root · connected to founder</option>{employees.filter(e=>e.department_id===department).map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><label>Why is this role needed?<textarea name="requirement" minLength={10} maxLength={3000} required placeholder="Describe the project requirement and expected work."/></label><p>This creates an AI profile and records the requirement. Model access and execution permissions are configured separately.</p><button className="btn" disabled={sending||!department}>Create role</button><button type="button" className="btn" onClick={()=>setStaffing(false)}>Cancel</button></form></section></div>}
  </section>;
}
