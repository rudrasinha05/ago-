"use client";
import Link from 'next/link';
import {useCallback,useEffect,useMemo,useRef,useState} from 'react';
import {resource} from '@ago/sdk/session';
import {employeeStatus,companyLayout,companyLinkAnchors,activeRouteKeys,employeeProjects} from '@ago/sdk/company';
import {CommandBrain,CompanyBoard} from './command-brain';
import {RoleEditor,UpwardReports} from './company-governance';
import {FounderProjectIntake} from './founder-project-intake';
import {CompanyApprovals} from './company-approvals';
import {CompanyApprovalBadge} from './company-approval-badge';
import {ManagementWorkload} from './company-management';
import {CompanyExecutionDesk} from './company-execution-desk';
import {CompanyGithubDelivery} from './company-github-delivery';
import {CompanyRolePlanner} from './company-role-planner';
import {OpportunityRadar} from './company-opportunities';
import {CompanyNotificationCenter,mergeNotificationPage} from './company-notification-center';
import {treeCompanyLayout,departmentCompanyLayout,circularDepartmentLayout,withMembership,departmentColors,MAP_VIEWS} from './company-layouts';
const BASE='/v1/organization/company';
const time=value=>new Date(value).toLocaleString();
export function CompanyMap({api,me,data,onRefresh}) {
  const rawDepartments=resource(data,'departments');
  // Stable identity when unavailable, so layout and colour memos do not rebuild every render.
  const departments=useMemo(()=>rawDepartments||[],[rawDepartments]);
  const grouped=resource(data,'employees');
  const employees=useMemo(()=>Object.values(grouped||{}).flat(),[grouped]);
  const founderView=me.roles?.includes('founder');
  // Poll only what this role may read: the server stays the authority, but
  // re-requesting a forbidden resource every few seconds is wasted load and
  // a constant stream of 403s in logs.
  const can=(...needed)=>needed.every(p=>me.permissions?.includes(p));
  const canActivity=can('brain:read','organization:read','task:read');
  const canChat=can('organization:read','task:read','messages:read');
  const canEvents=can('organization:read','task:read');
  const canGovernance=can('organization:read');
  const canTools=can('tool:read');
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
  const [zoom,setZoomState]=useState(.72),[pan,setPanState]=useState({x:0,y:0}),[staffing,setStaffing]=useState(false),[department,setDepartment]=useState('');
  const [mapMode,setMapMode]=useState('leadership'),[mapView,setMapView]=useState('circular');
  const [fullscreen,setFullscreen]=useState(false),[inspectorOpen,setInspectorOpen]=useState(true);
  const [addingDepartment,setAddingDepartment]=useState(false);
  const [updated,setUpdated]=useState(null),[popup,setPopup]=useState(null),[loading,setLoading]=useState(false);
  const [eventData,setEventData]=useState(null),[eventQueue,setEventQueue]=useState([]);const [githubState,setGithubState]=useState(null),[governanceData,setGovernanceData]=useState(null);const lastEvent=useRef(null);
  const viewport=useRef(null),drag=useRef(null),previous=useRef(null),sequence=useRef(0),alive=useRef(false),retry=useRef(null),feed=useRef(null),staffKey=useRef(null);
  const pendingFocus=useRef(null),mapInitialized=useRef(false),userMoved=useRef(false);
  // Live zoom/pan for wheel, pinch and drag handlers that fire faster than renders.
  const zoomRef=useRef(.72),panRef=useRef({x:0,y:0}),pointers=useRef(new Map()),gesture=useRef(null),suppressClick=useRef(false);
  const setZoom=useCallback(value=>{const next=typeof value==='function'?value(zoomRef.current):value;zoomRef.current=next;setZoomState(next);},[]);
  const setPan=useCallback(value=>{const next=typeof value==='function'?value(panRef.current):value;panRef.current=next;setPanState(next);},[]);
  const visibleEmployees=useMemo(()=>{
    if(mapMode==='all')return employees;
    const byId=new Map(employees.map(e=>[e.id,e]));
    const managerialIds=new Set(employees.filter(e=>employees.some(x=>x.manager_id===e.id)).map(e=>e.id));
    const included=new Set([
      ...(governanceData?.board||[]).map(b=>b.employee_id),
      ...managerialIds,
      ...employees.filter(e=>/chief |project manager|director|head of |founder/i.test(String(e.role_title||'')+' '+String(e.name||''))).map(e=>e.id),
      ...(Array.isArray(tasks)?tasks.filter(t=>['running','ready','waiting_approval','proposed'].includes(t.status)).map(t=>t.assignee_id):[]),
      ...(selected?[selected]:[]),
    ]);
    // Never draw a false department-root link when a real manager is hidden.
    for(const id of [...included]){
      let current=byId.get(id),seen=new Set();
      while(current?.manager_id&&byId.has(current.manager_id)&&!seen.has(current.manager_id)){
        seen.add(current.manager_id);included.add(current.manager_id);
        current=byId.get(current.manager_id);
      }
    }
    return employees.filter(e=>included.has(e.id)||e.id===me.id);
  },[employees,governanceData,mapMode,tasks,selected,me.id]);
  const layout=useMemo(()=>{
    // Every view re-positions the same validated graph; links never change.
    // Membership links (department_id) are added once and shown in every view.
    const base=withMembership(companyLayout(departments,visibleEmployees,me.id));
    return mapView==='tree'?treeCompanyLayout(base):mapView==='departments'?departmentCompanyLayout(base):circularDepartmentLayout(base);
  },[departments,visibleEmployees,me.id,mapView]);
  const deptColor=useMemo(()=>departmentColors(departments),[departments]);
  const deptName=useMemo(()=>new Map(departments.map(d=>[d.id,d.name])),[departments]);
  const points=new Map([['founder',layout.founder],...layout.nodes.map(n=>[n.key,n])]);
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
  const orbitRadii=useMemo(()=>layout.layout==='circular'?[...new Set(layout.nodes.map(n=>Math.round(n.radius)))].sort((a,b)=>a-b):[],[layout]);
  const selectedReportingIssue=layout.reportingIssues?.find(issue=>issue.employee_id===selected);
  const liveTaskCount=Array.isArray(tasks)?tasks.filter(t=>t.status==='running').length:0;
  const pendingTaskCount=Array.isArray(tasks)?tasks.filter(t=>['proposed','ready','waiting_approval'].includes(t.status)).length:0;
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
    if(!canActivity){setTasks(null);setUpdated(null);return;}
    try {const result=await api.request(BASE+'/activity');if(!alive.current)return;
      previous.current=new Map(result.map(t=>[t.id,t.status]));setTasks(result);setUpdated(new Date());
    }catch{if(alive.current){setTasks(null);setUpdated(null);}}
  },[api,canActivity]);
  useEffect(()=>{alive.current=true;refreshActivity();if(!canActivity)return()=>{alive.current=false;};
    const timer=setInterval(refreshActivity,7000);return()=>{alive.current=false;clearInterval(timer);};},[refreshActivity,canActivity]);
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
    if(!canChat){setLoading(false);setError('Conversations are not available for your role.');return()=>{live=false;};}
    fetchMessages(true);const timer=setInterval(fetchMessages,5000);
    return()=>{live=false;clearInterval(timer);};
  },[api,channel,canChat]);
  const refreshEvents=useCallback(async()=>{
    if(!canEvents){setEventData(null);return;}
    try{
      const previousId=lastEvent.current;
      const path=BASE+'/notifications'+(previousId===null?'':'?after_id='+previousId);
      const next=await api.request(path);
      if(!alive.current)return;
      if(previousId!==null){
        // API returns forward cursor pages, never drop old queued popups.
        const fresh=(next.recent||[]).filter(e=>e.id>previousId);
        if(fresh.length){
          setEventQueue(old=>[...old,...fresh]);
          lastEvent.current=fresh[fresh.length-1].id;
        }
      }else{
        // Initial boot starts from the newest known persisted ID; historic
        // events remain visible through the notification ledger and badges.
        lastEvent.current=next.recent?.[0]?.id||0;
      }
      // Cursor pages hold only new events: merge so earlier events stay visible.
      setEventData(old=>previousId===null?mergeNotificationPage(null,next):mergeNotificationPage(old,next));
    }catch{if(alive.current)setEventData(null);}
  },[api,canEvents]);
  useEffect(()=>{refreshEvents();if(!canEvents)return undefined;const timer=setInterval(refreshEvents,7000);return()=>clearInterval(timer);},[refreshEvents,canEvents]);
  const refreshGovernance=useCallback(async()=>{
    if(!canGovernance){setGovernanceData(null);return;}
    try {const result=await api.request(BASE+'/governance');if(alive.current)setGovernanceData(result);}
    catch {if(alive.current)setGovernanceData(null);}
  },[api,canGovernance]);
  useEffect(()=>{refreshGovernance();},[refreshGovernance]);
  async function appointBoard(seat,employeeId){
    setError('');
    try {await api.request(BASE+'/board/appoint',{method:'POST',body:{seat,employee_id:employeeId}});await refreshGovernance();}
    catch(e){setError(e.message);}
  }
  const refreshGitHub=useCallback(async()=>{
    if(!canTools){setGithubState(null);return;}
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
  },[api,canTools]);
  useEffect(()=>{refreshGitHub();if(!canTools)return undefined;const timer=setInterval(refreshGitHub,45000);return()=>clearInterval(timer);},[refreshGitHub,canTools]);
  useEffect(()=>{if(!popup&&eventQueue.length){setPopup(eventQueue[0]);setEventQueue(old=>old.slice(1));}},[popup,eventQueue]);
  useEffect(()=>{if(!popup)return;const timer=setTimeout(()=>setPopup(null),6500);return()=>clearTimeout(timer);},[popup]);
  function focusMap(key,scale=.8){
    const target=key==='founder'?layout.founder:layout.nodes.find(n=>n.key===key);
    if(!target)return false;
    userMoved.current=true;
    setZoom(scale);
    setPan(boundedPan((layout.center-target.x)*scale,(layout.center-target.y)*scale,scale));
    return true;
  }
  function fitMap(){
    const w=viewport.current?.clientWidth||700,h=viewport.current?.clientHeight||700;
    // Fit the occupied area, not the whole orbit canvas: a small company must
    // stay readable instead of shrinking to a few pixels inside empty rings.
    const placed=[layout.founder,...layout.nodes,...(layout.wedges||[]).map(w=>w.label)].filter(n=>Number.isFinite(n?.x)&&Number.isFinite(n?.y));
    const margin=170;
    const xs=placed.map(n=>n.x),ys=placed.map(n=>n.y);
    const minX=Math.min(...xs)-margin,maxX=Math.max(...xs)+margin,minY=Math.min(...ys)-margin,maxY=Math.max(...ys)+margin;
    // The control bar and legend float over the map: fit into the clear area between them.
    const top=(viewport.current?.querySelector('.map-controls')?.offsetHeight||0)+12;
    const bottom=(viewport.current?.querySelector('.map-legend')?.offsetHeight||0)+12;
    const clear=Math.max(120,h-top-bottom),shiftY=(top-bottom)/2;
    const fit=placed.length?Math.max(.055,Math.min(.9,w/(maxX-minX)*.94,clear/(maxY-minY)*.94))
      :Math.max(.055,Math.min(1,Math.min(w,clear)/layout.size*.92));
    setZoom(fit);
    setPan(placed.length?boundedPan((layout.center-(minX+maxX)/2)*fit,(layout.center-(minY+maxY)/2)*fit+shiftY,fit):{x:0,y:shiftY});
  }
  useEffect(()=>{
    if(pendingFocus.current==='overview'){
      fitMap();pendingFocus.current=null;
    }else if(pendingFocus.current){
      if(pendingFocus.current==='founder'||layout.nodes.some(n=>n.key===pendingFocus.current)){
        focusMap(pendingFocus.current,.82);
        pendingFocus.current=null;
      }
    }else if((!mapInitialized.current||!userMoved.current)&&employees.length>1){
      // Keep fitting as records load (governance, tasks, mode) until the
      // person zooms, pans or focuses a node themselves.
      mapInitialized.current=true;
      fitMap();
    }
  },[layout]);
  function choose(key){if(!canReadChannel(key)){setError('This AGO conversation is private to its authorized participants.');return;}setChannel(key);setReply(null);setInspectorOpen(true);if(key.startsWith('employee:'))setSelected(key.slice(9));if(!focusMap(key,.84)&&key.startsWith('employee:')){pendingFocus.current=key;setMapMode('all');}
    // People, teams and conversations live on the Organization tab: show it.
    if(activeTab!=='ago-tab-organization'){setActiveTab('ago-tab-organization');
      requestAnimationFrame(()=>document.getElementById('ago-company-org-map')?.scrollIntoView({block:'start',behavior:'auto'}));}}
  function boundedPan(x,y,z=zoomRef.current){
    const w=viewport.current?.clientWidth||700,h=viewport.current?.clientHeight||700;
    // Allow up to half the drawn canvas off-centre so any part can be brought
    // to the middle at any zoom; still never lose the map entirely.
    const maxX=Math.max(0,(layout.size*z-w)/2)+Math.max(w/2,layout.size*z/2);
    const maxY=Math.max(0,(layout.size*z-h)/2)+Math.max(h/2,layout.size*z/2);
    return {x:Math.max(-maxX,Math.min(maxX,x)),y:Math.max(-maxY,Math.min(maxY,y))};
  }
  /** Zoom keeping the world point under (cx,cy) fixed; centre when no point. */
  function zoomOn(next,cx=null,cy=null){
    // The person took control: never let a queued automatic fit undo it.
    userMoved.current=true;pendingFocus.current=null;
    const current=zoomRef.current;
    next=Math.max(.05,Math.min(2.5,next));
    if(next===current)return;
    const rect=viewport.current?.getBoundingClientRect();
    const dx=rect&&cx!==null?cx-rect.left-rect.width/2:0;
    const dy=rect&&cy!==null?cy-rect.top-rect.height/2:0;
    const p=panRef.current;
    setPan(boundedPan(dx-(dx-p.x)*next/current,dy-(dy-p.y)*next/current,next));
    setZoom(next);
  }
  const zoomOnRef=useRef(zoomOn);zoomOnRef.current=zoomOn;
  // Native non-passive wheel listener: zoom at the cursor without scrolling the
  // page. Attached through a callback ref so it follows the real canvas node.
  const wheelCleanup=useRef(null);
  const canvasRef=useCallback(element=>{
    wheelCleanup.current?.();wheelCleanup.current=null;
    viewport.current=element;
    if(!element)return;
    const onWheel=e=>{
      if(e.target.closest?.('textarea,.map-legend'))return;
      e.preventDefault();
      const factor=Math.exp(-Math.max(-60,Math.min(60,e.deltaMode===1?e.deltaY*16:e.deltaY))*.0022);
      zoomOnRef.current(zoomRef.current*factor,e.clientX,e.clientY);
    };
    element.addEventListener('wheel',onWheel,{passive:false});
    wheelCleanup.current=()=>element.removeEventListener('wheel',onWheel);
  },[]);
  const INTERACTIVE='textarea,input,select,label,form button,.map-controls,.map-legend,.employee-approval-zone';
  function mapPointerDown(e){
    if(e.button!==undefined&&e.button!==0&&e.pointerType==='mouse')return;
    if(e.target.closest(INTERACTIVE))return;
    pointers.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
    if(pointers.current.size===2){
      const [a,b]=[...pointers.current.values()];
      gesture.current={type:'pinch',distance:Math.hypot(a.x-b.x,a.y-b.y)||1,zoom:zoomRef.current};
      suppressClick.current=true;
    }else if(pointers.current.size===1){
      gesture.current={type:'pending',x:e.clientX,y:e.clientY,startX:panRef.current.x,startY:panRef.current.y,id:e.pointerId};
    }
  }
  function mapPointerMove(e){
    if(!pointers.current.has(e.pointerId))return;
    pointers.current.set(e.pointerId,{x:e.clientX,y:e.clientY});
    const g=gesture.current;if(!g)return;
    if(g.type==='pinch'&&pointers.current.size>=2){
      const [a,b]=[...pointers.current.values()];
      const distance=Math.hypot(a.x-b.x,a.y-b.y)||1;
      zoomOn(g.zoom*distance/g.distance,(a.x+b.x)/2,(a.y+b.y)/2);
      return;
    }
    if(g.type==='pending'&&Math.hypot(e.clientX-g.x,e.clientY-g.y)>5){
      // Became a drag: pan from any point, including over employee cards.
      g.type='pan';userMoved.current=true;pendingFocus.current=null;suppressClick.current=true;
      e.currentTarget.setPointerCapture?.(e.pointerId);
    }
    if(g.type==='pan')setPan(boundedPan(g.startX+(e.clientX-g.x),g.startY+(e.clientY-g.y)));
  }
  function mapPointerEnd(e){
    pointers.current.delete(e.pointerId);
    if(e.currentTarget.hasPointerCapture?.(e.pointerId))e.currentTarget.releasePointerCapture(e.pointerId);
    if(pointers.current.size===1&&gesture.current?.type==='pinch'){
      // Continue as a pan with the remaining finger.
      const [[id,point]]=[...pointers.current.entries()];
      gesture.current={type:'pan',x:point.x,y:point.y,startX:panRef.current.x,startY:panRef.current.y,id};
    }else if(!pointers.current.size)gesture.current=null;
  }
  // The canvas clips the map (overflow:hidden) but the browser still scrolls
  // it to reveal a keyboard-focused card. That shifts the whole map with no
  // way back. Turn any such scroll into a pan so focus stays visible and the
  // map stays consistent.
  function mapScroll(e){
    const el=e.currentTarget,dx=el.scrollLeft,dy=el.scrollTop;
    if(!dx&&!dy)return;
    el.scrollLeft=0;el.scrollTop=0;
    userMoved.current=true;pendingFocus.current=null;
    setPan(p=>boundedPan(p.x-dx,p.y-dy));
  }
  // Keyboard focus may land on a card outside the visible map in any
  // direction (the browser cannot scroll to negative offsets): pan to it.
  function mapFocus(e){
    const el=e.target,box=e.currentTarget.getBoundingClientRect(),r=el.getBoundingClientRect?.();
    if(!r||el===e.currentTarget||el.closest('.map-controls,.map-legend'))return;
    const inside=r.left>=box.left&&r.right<=box.right&&r.top>=box.top&&r.bottom<=box.bottom;
    if(inside)return;
    const dx=(box.left+box.width/2)-(r.left+r.width/2),dy=(box.top+box.height/2)-(r.top+r.height/2);
    userMoved.current=true;pendingFocus.current=null;
    setPan(p=>boundedPan(p.x+dx,p.y+dy));
  }
  function mapClickCapture(e){
    // A drag or pinch must not also open the card it ended on.
    if(suppressClick.current){suppressClick.current=false;e.preventDefault();e.stopPropagation();}
  }
  function center(){focusMap('founder',.72);}
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
  // Organization tabs: every section stays mounted (polling, drafts and
  // selection survive switching); only the active panel is shown. Any
  // in-page link to a section id opens the tab that contains it.
  const [activeTab,setActiveTab]=useState('ago-tab-command');
  const pendingApprovals=(approvalList||[]).filter(a=>a.status==='pending').length;
  const tabs=[
    {id:'ago-tab-command',label:'Command Center'},
    {id:'ago-tab-approvals',label:'Approvals',badge:pendingApprovals||null,badgeLabel:pendingApprovals+' pending approval requests'},
    ...((founderView&&me.permissions?.includes('brain:manage'))||(me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read'))
      ?[{id:'ago-tab-projects',label:'Projects'}]:[]),
    ...(me.permissions?.includes('task:read')||founderView?[{id:'ago-tab-delivery',label:'Execution & Delivery',badge:liveTaskCount||null,badgeLabel:liveTaskCount+' tasks running'}]:[]),
    {id:'ago-tab-board',label:'Board & Roles'},
    {id:'ago-tab-organization',label:'Organization & Chat'},
  ];
  const openSection=useCallback((id,{updateHash=false}={})=>{
    const target=document.getElementById(id);
    const panel=target?.matches?.('[data-tab-panel]')?target:target?.closest?.('[data-tab-panel]');
    if(!panel)return false;
    setActiveTab(panel.id);
    if(updateHash&&window.location.hash!=='#'+id)history.replaceState(history.state,'',window.location.pathname+window.location.search+'#'+id);
    // Scroll after the panel is shown; a panel itself scrolls to the tab bar.
    requestAnimationFrame(()=>{
      const node=document.getElementById(id);
      (node?.matches?.('[data-tab-panel]')?document.querySelector('.company-tabs'):node)?.scrollIntoView({block:'start',behavior:'auto'});
    });
    return true;
  },[]);
  useEffect(()=>{
    const fromHash=()=>{const id=decodeURIComponent(window.location.hash.slice(1));if(/^[A-Za-z0-9_-]+$/.test(id))openSection(id);};
    fromHash();
    window.addEventListener('hashchange',fromHash);
    return()=>window.removeEventListener('hashchange',fromHash);
  },[openSection]);
  useEffect(()=>{
    // The map measures its viewport; re-fit once it becomes visible.
    if(activeTab==='ago-tab-organization'&&!userMoved.current)requestAnimationFrame(()=>fitMap());
  },[activeTab]);
  async function hire(event){event.preventDefault();const form=new FormData(event.currentTarget);
    const values={department_id:department,manager_id:form.get('manager')||null,name:form.get('name'),requirement:form.get('requirement')};
    const signature=JSON.stringify(values);if(staffKey.current?.signature!==signature)staffKey.current={signature,key:crypto.randomUUID()};
    setSending(true);try{const hired=await api.request(BASE+'/staffing',{method:'POST',body:{...values,operation_key:staffKey.current.key}});staffKey.current=null;setStaffing(false);if(hired?.id){pendingFocus.current='employee:'+hired.id;setMapMode('all');}await onRefresh();}
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
  return <section id="ago-unified-cockpit" className="company-command" aria-label="Company map and conversations"
    onClick={event=>{
      // Every in-page section link (tab bar or "View approval inbox ↑" style
      // links inside sections) opens the tab holding that section. Fragment
      // navigation never reloads a tab-memory AGO session.
      const anchor=event.target.closest?.('a[href^="#"]');
      const fragment=anchor?.getAttribute('href');
      if(!fragment||!/^#[A-Za-z0-9_-]+$/.test(fragment))return;
      if(!document.getElementById(fragment.slice(1))?.closest?.('[data-tab-panel]'))return;
      event.preventDefault();
      openSection(fragment.slice(1),{updateHash:true});
    }}>
    <header className="company-heading"><div><p className="eyebrow">FOUNDER OPERATIONS · EVIDENCE BASED</p><h1>Company map</h1><p>Owner prompts, delegated work, review and accountable delivery.</p></div><div className="company-heading-actions">
      <CompanyNotificationCenter api={api} data={eventData} employees={employees} onSelect={id=>choose('employee:'+id)}
        onRead={result=>{setEventData(old=>old&&Number.isInteger(result?.read_through_id)?{...old,read_through_id:result.read_through_id,
          unread_count:(old.recent||[]).filter(e=>e.id>result.read_through_id).length}:old);refreshEvents();}}/>
      {me.permissions.includes('organization:manage')&&<><button type="button" className="btn" aria-expanded={addingDepartment} onClick={()=>setAddingDepartment(v=>!v)}>Add department</button><button type="button" className="btn" disabled={!departments.length} onClick={()=>{setDepartment(departments[0]?.id||'');setStaffing(true);}}>Add needed role</button></>}</div></header>
    {addingDepartment&&me.permissions.includes('organization:manage')&&<form className="company-add-department" onSubmit={createDepartment}><label htmlFor="company-department-name">Department name</label><input id="company-department-name" name="name" autoFocus required maxLength={150} placeholder="e.g. Engineering"/><button className="btn" disabled={sending}>{sending?'Saving…':'Create department'}</button><button type="button" className="btn" onClick={()=>setAddingDepartment(false)}>Cancel</button></form>}
    <nav className="company-cockpit-nav company-tabs" aria-label="Company control center sections">
      {tabs.map(tab=><a key={tab.id} href={'#'+tab.id} aria-current={activeTab===tab.id?'page':undefined}
        className={activeTab===tab.id?'active':undefined}>
        {tab.label}{tab.badge?<><b className="company-tab-badge" aria-hidden="true">{tab.badge}</b><span className="sr-only">, {tab.badgeLabel}</span></>:null}
      </a>)}
    </nav>
    <section id="ago-tab-command" className="company-tab-panel" data-tab-panel aria-label="Command Center" hidden={activeTab!=='ago-tab-command'}>
    <CommandBrain tasks={tasks} notifications={eventData} employees={employees} departments={departments} founderId={me.id} selectedId={selected} onSelect={id=>choose('employee:'+id)}/>
    </section>
    <section id="ago-tab-approvals" className="company-tab-panel" data-tab-panel aria-label="Approvals" hidden={activeTab!=='ago-tab-approvals'}>
    <CompanyApprovals api={api} me={me} employees={employees} onData={receiveApprovalData} refreshSignal={approvalRefresh} onReviewed={refreshEvents}/>
    </section>
    <section id="ago-tab-projects" className="company-tab-panel" data-tab-panel aria-label="Projects" hidden={activeTab!=='ago-tab-projects'}>
    {/* Jump links only for sections this role can actually see. */}
    <nav className="company-subnav" aria-label="Projects sections">
      {founderView&&me.permissions?.includes('brain:manage')&&<a href="#ago-project-portfolio">Project portfolio</a>}
      {me.permissions?.includes('organization:read')&&me.permissions?.includes('brain:read')&&<a href="#ago-opportunities">Business opportunities</a>}
    </nav>
    <FounderProjectIntake api={api} me={me} employees={employees} profiles={governanceData?.employees||[]} onChanged={()=>setApprovalRefresh(v=>v+1)}/>
    <OpportunityRadar api={api} me={me} onChanged={()=>setApprovalRefresh(x=>x+1)}/>
    </section>
    <section id="ago-tab-delivery" className="company-tab-panel" data-tab-panel aria-label="Execution and delivery" hidden={activeTab!=='ago-tab-delivery'}>
    <nav className="company-subnav" aria-label="Execution and delivery sections">
      {me.permissions?.includes('task:read')&&<a href="#ago-execution-desk">Execution desk</a>}
      {me.permissions?.includes('task:read')&&<a href="#ago-workforce">Workforce</a>}
      {founderView&&<a href="#ago-github-delivery">Project delivery</a>}
    </nav>
     <CompanyExecutionDesk api={api} me={me} tasks={tasks} approvals={approvalList} employees={employees} onChange={async()=>{await refreshActivity();await refreshEvents();setApprovalRefresh(v=>v+1);}} onEmployee={id=>choose('employee:'+id)}/>
     <ManagementWorkload api={api} me={me} refreshSignal={approvalRefresh}/>
     {founderView&&<CompanyGithubDelivery api={api} me={me}/>} 
    </section>
    <section id="ago-tab-board" className="company-tab-panel" data-tab-panel aria-label="Board and roles" hidden={activeTab!=='ago-tab-board'}>
    <CompanyBoard employees={employees} governance={governanceData} canGovern={me.roles.includes('founder')} onAppoint={appointBoard} onSelect={id=>choose('employee:'+id)}/>
    <CompanyRolePlanner api={api} me={me} employees={employees} departments={departments} profiles={governanceData?.employees??null} board={governanceData?.board||[]} onSaved={async()=>{await refreshGovernance();await onRefresh();}}/>
    </section>
    <section id="ago-tab-organization" className="company-tab-panel" data-tab-panel aria-label="Organization and chat" hidden={activeTab!=='ago-tab-organization'}>
    <div id="ago-company-org-map" className={"company-shell"+(fullscreen?" company-fullscreen":"")} aria-label="Organization map workspace">
      <aside className="company-channels" aria-label="Conversation channels"><h2>Conversations</h2><input aria-label="Find department or employee" placeholder="Find a person or team…" value={query} onChange={e=>setQuery(e.target.value)}/>
        <button className={channel==='global'?'chosen':''} onClick={()=>choose('global')}>◉ Global timeline</button>
        {departments.map(d=>{const members=employees.filter(e=>e.department_id===d.id);if(query&&!d.name.toLowerCase().includes(query.toLowerCase())&&!members.some(e=>e.name.toLowerCase().includes(query.toLowerCase())))return null;
          function branch(e,seen=new Set()){if(seen.has(e.id))return null;const next=new Set([...seen,e.id]);return <li key={e.id}><button aria-label={e.name} className={[channel==='employee:'+e.id?'chosen':'',routing.active.has(e.id)?'chat-assigned':'',employeeStatus(e.id,tasks).tone==='busy'?'chat-working':''].filter(Boolean).join(' ')} onClick={()=>choose('employee:'+e.id)}><span className={'presence '+employeeStatus(e.id,tasks).tone}/>{e.name}{(eventData?.by_employee?.[e.id]??0)>0&&<span className="chat-event-count" aria-label={(eventData?.by_employee?.[e.id]??0)+" recorded work events"}>{eventData.by_employee[e.id]}</span>}</button><ul>{members.filter(x=>x.manager_id===e.id).map(x=>branch(x,next))}</ul></li>;}
          if(!canReadChannel('department:'+d.id))return null;
          return <details key={d.id} open><summary>{d.name}</summary><button onClick={()=>choose('department:'+d.id)} className={channel==='department:'+d.id?'chosen':''}>Open {d.name} chat</button><ul>{members.filter(e=>!members.some(x=>x.id===e.manager_id)).map(e=>branch(e))}</ul></details>;})}
        <p className="channel-note">Global chat is shared. Department and employee conversations are restricted to the founder and authorized members. AGO enforces access on every read and write.</p>
      </aside>
      <div className="company-canvas" ref={canvasRef} onPointerDown={mapPointerDown} onPointerMove={mapPointerMove} onPointerUp={mapPointerEnd} onPointerCancel={mapPointerEnd} onClickCapture={mapClickCapture} onScroll={mapScroll} onFocusCapture={mapFocus} onDoubleClick={e=>{if(!e.target.closest('.map-node-wrap,.map-founder,.map-controls,.map-legend'))zoomOn(zoomRef.current*1.6,e.clientX,e.clientY);}}>
        <div className="map-controls">
          <button aria-label="Zoom in" onClick={()=>zoomOn(zoomRef.current*1.25)}>+</button>
          <button aria-label="Zoom out" onClick={()=>zoomOn(zoomRef.current/1.25)}>−</button>
          <span className="map-view-switch" role="group" aria-label="Map view">{MAP_VIEWS.map(([key,label,hint])=>
            <button key={key} type="button" title={hint} aria-pressed={mapView===key}
              onClick={()=>{if(mapView===key)return;setMapView(key);userMoved.current=false;pendingFocus.current='overview';}}>{label}</button>)}</span>
          <button onClick={center}>Founder</button>
          <button type="button" aria-pressed={mapMode==='leadership'} onClick={()=>{if(mapMode==='leadership')return;setMapMode('leadership');pendingFocus.current='overview';}}>Leadership</button>
          <button type="button" aria-pressed={mapMode==='all'} onClick={()=>{if(mapMode==='all')return;setMapMode('all');pendingFocus.current='overview';}}>All employees</button>
          <button aria-label={fullscreen?"Exit full screen":"Full screen map"} aria-pressed={fullscreen} onClick={()=>setFullscreen(v=>!v)}>{fullscreen?"Exit full screen":"⛶ Full screen"}</button>
          <button onClick={()=>{userMoved.current=false;fitMap();}}>Fit all</button>
          <span>{layout.nodes.filter(n=>n.type==='employee').length}/{employees.filter(e=>e.id!==me.id).length} staff · {Math.round(zoom*100)}%</span>
        </div>
        <div className={'company-world view-'+layout.layout+(zoom<.38?' lod-far':'')} style={{width:layout.size,height:layout.size,'--lod':zoom<.38?Math.min(layout.layout==='tree'?1.25:layout.layout==='departments'?1.45:1.7,.4/zoom):1,transform:`translate(calc(-50% + ${pan.x}px),calc(-50% + ${pan.y}px)) scale(${zoom})`}}>
          <svg width={layout.size} height={layout.size} aria-label={(layout.layout==='tree'?'Tree organisation chart.':layout.layout==='departments'?'Department lanes.':'Circular organizational hierarchy.')+" Blue links are actual recorded reporting lines; grey dotted links show grouping only. Red marks running tasks on recorded reporting routes."}>
           <defs><marker id="ago-report-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 1 L9 5 L0 9Z" fill="#65bfe8"/></marker></defs>
           {(layout.wedges||[]).map(w=><g key={w.key} className="department-wedge" style={{'--dept':deptColor.get(w.departmentId)||'#7e91a9'}}>
             <path d={w.path}/><text x={w.label.x} y={w.label.y} textAnchor="middle" dominantBaseline="middle">{deptName.get(w.departmentId)||'Department'}</text></g>)}
           {orbitRadii.map(radius=><circle key={radius} className="company-orbit-ring" cx={layout.center} cy={layout.center} r={radius}/>)}
           {layout.edges.map((edge,i)=>{
             const a=points.get(edge.from),b=points.get(edge.to),key=edge.from+'>'+edge.to;
             const mode=routing.routes.has(key)?'running':routing.waitingRoutes.has(key)?'pending':null;
             const open=()=>choose(edge.to);
             const grouping=edge.kind==='grouping';
             if(!a||!b)return null;
             const anchor=edge.path?{cx:edge.mid.x,cy:edge.mid.y}:companyLinkAnchors(a,b,edge.from==='founder'?'founder':a.type,b.type);
             const member=edge.from.startsWith('department:');
             const kindClass=edge.kind==='membership'?'membership-link':edge.kind==='unassigned'?'unassigned-link':grouping?'department-link':'manager-link';
             const linkProps={'data-link-kind':edge.kind,
               className:['company-link',kindClass,member?'member-link':'',mode==='running'?'edge-live':mode==='pending'?'edge-pending':''].filter(Boolean).join(' '),
               style:member?{'--dept':deptColor.get(edge.from.slice(11))||'#7e91a9'}:undefined,
               markerEnd:edge.kind==='reporting'?'url(#ago-report-arrow)':undefined,
               'data-route-target':mode?edge.to:undefined,onClick:mode?open:undefined};
             const linkTitle=<title>{edge.kind==='membership'||member?'Department member (recorded department), not a reporting line'
               :edge.kind==='unassigned'?'No manager recorded — placed under the Founder for layout only'
               :grouping?'Grouping only (not a management reporting line)':'Recorded manager reporting link'}{mode?' · '+mode+' task route':''}</title>;
             return <g key={i}>{edge.path?<path {...linkProps} d={edge.path} fill="none">{linkTitle}</path>
               :<line {...linkProps} x1={anchor.x1} y1={anchor.y1} x2={anchor.x2} y2={anchor.y2}>{linkTitle}</line>}
             </g>;
           })}</svg>
          <form className="map-founder" style={{left:layout.founder.x,top:layout.founder.y,transform:`translate(-50%,-50%) scale(${Math.max(1,Math.min(1.8,.75/zoom))})`}} onSubmit={e=>send(e,true)}><CompanyApprovalBadge employee={{id:me.id,name:'Founder'}} approvals={approvalList} updates={0} api={api} me={me} onDone={async()=>{setApprovalRefresh(v=>v+1);await refreshActivity();await refreshEvents();}}/><strong>♛ Founder · Human authority</strong><small>{employees.find(e=>e.id===me.id)?.name||'Company centre'}</small><label htmlFor="founder-message">Talk to your company</label><textarea id="founder-message" value={centerDraft} onChange={e=>setCenterDraft(e.target.value)} maxLength={20000} placeholder="Your idea, project or question…" rows={3}/><button disabled={sending||!centerDraft.trim()} className="btn">Send to global chat</button></form>
          {layout.nodes.map(n=>{const state=employeeStatus(n.id,tasks);
             const project=displayProjects(n.id);const eventCount=eventData?.by_employee?.[n.id]??0;
             const recordedRole=governanceData?.employees?.find(e=>e.id===n.id)?.role_title;
             const approvalCount=(approvalList||[]).filter(a=>a.requester_id===n.id&&a.status==='pending').length;
             const color=deptColor.get(n.type==='department'?n.id:n.department_id);
             return <div key={n.key} className="map-node-wrap" style={{left:n.x,top:n.y,'--dept':color||'#7e91a9'}}><button type="button" aria-label={n.type==='employee'?n.name+', '+state.label+', '+eventCount+' recorded updates':n.name} className={'map-node '+n.type+(channel===n.key?' active':'')+(n.type==='employee'&&state.tone==='busy'?' working':'')+(routing.active.has(n.id)?' assigned':'')} onClick={()=>choose(n.key)}>
               {n.type==='employee'&&eventCount>0&&<span className="map-count" title="Recorded work events">{eventCount}</span>}
               <strong>{n.type==='employee'&&<span className={'presence '+state.tone}/>} {n.name}</strong>
               <small>{n.type==='department'?'Department · '+employees.filter(e=>e.department_id===n.id).length+' members':(n.kind==='ai'?'AI employee · ':'Human member · ')+state.label}</small>
               {n.type==='employee'&&<small className="map-dept">{deptName.get(n.department_id)||'No department'}</small>}
               {n.type==='employee'&&<small className="map-role">Role: {recordedRole||'Not assigned'}</small>}
               {n.type==='employee'&&approvalCount>0&&<small className="map-role">{approvalCount} pending approval request(s)</small>}
               {n.type==='employee'&&<small className="map-project">Project: {project[0]||'No linked project'}{project.length>1?' +'+(project.length-1):''}</small>}
               {n.type==='employee'&&state.tasks.find(t=>t.status==='running')&&<small className="map-task">{state.tasks.find(t=>t.status==='running').action}</small>}
               {n.type==='employee'&&<span className="node-action">View work details ↗</span>}
             </button>
              {n.type==='employee'&&<CompanyApprovalBadge employee={n} approvals={approvalList} updates={eventCount} api={api} me={me} zoom={zoom}
                onDone={async()=>{setApprovalRefresh(v=>v+1);await refreshActivity();await refreshEvents();}}/>}
             </div>;})}
          {/* Route targets sit above the cards so a running route is always clickable. */}
          <svg className="company-route-layer" width={layout.size} height={layout.size}>
           {layout.edges.map((edge,i)=>{
             const a=points.get(edge.from),b=points.get(edge.to),key=edge.from+'>'+edge.to;
             const mode=routing.routes.has(key)?'running':routing.waitingRoutes.has(key)?'pending':null;
             if(!mode||!a||!b)return null;
             const open=()=>choose(edge.to);
             const anchor=edge.path?{cx:edge.mid.x,cy:edge.mid.y}:companyLinkAnchors(a,b,edge.from==='founder'?'founder':a.type,b.type);
             return <g key={i}>
               <circle className={'route-hit-target '+mode} cx={anchor.cx} cy={anchor.cy} r={27} data-route-target={edge.to} role="button" tabIndex={0} aria-label={(mode==='running'?'Running route to ':'Pending route to ')+(b.name||'team')} onClick={open} onKeyDown={e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();open();}}}/>
             </g>;
           })}</svg>
        </div>
        <div className="map-legend" role="region" tabIndex={0} aria-label="Company graph status and link legend"><span><i className="presence idle"/>Idle</span><span><i className="presence busy"/>Busy</span><span><i className="presence waiting"/>Waiting</span><span><i className="presence blocked"/>Blocked</span><span><i className="presence failed"/>Failure recorded</span><span><i className="presence unknown"/>Unknown</span><span className="legend-live">━ Bright red: verified running task</span><span className="legend-pending">┄ Amber dashed: awaiting approval</span><span>━ Blue: verified manager record</span><span className="legend-member">━ Coloured: department membership (not reporting, no task routing)</span><span>┄ Grey dashed: no manager recorded</span><span>{liveTaskCount} running · {pendingTaskCount} waiting</span>{layout.reportingIssues?.length>0&&<span className="map-reporting-warning">{layout.reportingIssues.length} reporting relationship(s) unassigned or invalid — review the employee details</span>}<small>{updated?'Checked '+updated.toLocaleTimeString():'Activity unavailable'}</small></div>
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
           <dt>Reports to</dt><dd>{selectedReportingIssue?.reason==='reporting_cycle'?'Invalid reporting cycle — review required':selectedReportingIssue?.reason==='self_reporting'?'Invalid self-reporting — review required':selectedReportingIssue?.reason==='manager_not_in_roster'?'Manager unavailable in roster — review required':selectedEmployee.manager_id===me.id?'Founder (recorded)':employees.find(e=>e.id===selectedEmployee.manager_id)?.name||'No manager assigned (not a Founder report)'}</dd>
           <dt>Current projects</dt><dd>{displayProjects(selected).join(', ')||'No project linked'}</dd>
           <dt>Recorded updates</dt><dd>{eventData?.by_employee?.[selected]??'Unavailable'}</dd>
           <dt>Core responsibility</dt><dd>{governanceData?.employees?.find(e=>e.id===selected)?.core_responsibilities||'Not configured — use Company Role Planner.'}</dd>
           <dt>Additional responsibilities</dt><dd>{governanceData?.employees?.find(e=>e.id===selected)?.extra_responsibilities||'Not configured'}</dd></dl>
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
      <p>Commits, PRs, documentation and CI still require evidence and approval. Repository changes are never inferred from dashboard animations.</p><Link className="company-github-navigation" href="/tools/">View GitHub operations and CI →</Link></section></div>
    </section>
    {error&&<p role="alert" className="company-error">{error}</p>}
    {staffing&&<div className="staffing-backdrop"><section onKeyDown={e=>{if(e.key==='Escape')setStaffing(false);if(e.key==='Tab'){const controls=[...e.currentTarget.querySelectorAll('input,select,textarea,button')].filter(x=>!x.disabled);const first=controls[0],last=controls.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}}} role="dialog" aria-modal="true" aria-labelledby="staff-title" className="staffing-dialog"><h2 id="staff-title">Add a role your project needs</h2>{error&&<p role="alert">{error}</p>}<form onSubmit={hire}><label>Role name<input name="name" required maxLength={150} autoFocus placeholder="e.g. Research Scientist"/></label><label htmlFor="staff-department">Department</label><select id="staff-department" value={department} onChange={e=>setDepartment(e.target.value)} required><option value="">Choose department</option>{departments.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select><label htmlFor="staff-manager">Reports to</label><select id="staff-manager" name="manager" key={department}><option value="">Department root · connected to founder</option>{employees.filter(e=>e.department_id===department).map(e=><option key={e.id} value={e.id}>{e.name}</option>)}</select><label>Why is this role needed?<textarea name="requirement" minLength={10} maxLength={3000} required placeholder="Describe the project requirement and expected work."/></label><p>This creates an AI profile and records the requirement. Model access and execution permissions are configured separately.</p><button className="btn" disabled={sending||!department}>Create role</button><button type="button" className="btn" onClick={()=>setStaffing(false)}>Cancel</button></form></section></div>}
  </section>;
}
