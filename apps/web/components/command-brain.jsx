"use client";
import {useCallback,useMemo,useState} from 'react';
import {Brain3DScene,BRAIN_ZOOM} from './brain-3d-scene';
import {brainNetwork} from './brain-network';
import {boardFunctionSeats} from '@ago/sdk/company';

const brief=(text,max=110)=>text?.length>max?text.slice(0,max)+'…':text;
const BOARD_TITLES={
 'Strategy & Vision':'CEO · Chief Executive Officer',
 'Technology Oversight':'CTO · Chief Technology Officer',
 'Finance & Budget':'CFO · Chief Financial Officer',
 'Risk & Compliance':'CISO · Chief Information Security Officer',
 'Quality & Release':'CQO · Chief Quality Officer',
};
// These separate CSS 3D planes supply depth; only real running tasks illuminate nodes.
const CORTEX_CONTOUR='M199 247 C176 258 137 238 136 209 C93 205 82 164 110 139 C84 107 107 74 143 80 C149 44 194 39 207 65 C229 36 270 47 284 73 C323 62 347 92 337 119 C373 148 351 188 320 197 C323 228 293 251 266 239 C249 259 222 255 208 241Z';
const CORTEX_DEPTHS=[-75,-60,-45,-30,-15,0,15,30];
const CORTEX_POINTS=[[162,126],[254,106],[205,162],[269,197],[147,201],[295,137]];
const ago=value=>{
 const at=Date.parse(value);if(!Number.isFinite(at))return '';
 const seconds=Math.max(0,Math.round((Date.now()-at)/1000));
 if(seconds<60)return 'just now';if(seconds<3600)return Math.round(seconds/60)+' min ago';
 if(seconds<86400)return Math.round(seconds/3600)+' h ago';return new Date(at).toLocaleDateString();
};
const NEURON_FILTERS=[['all','All'],['working','Working'],['waiting','Waiting'],['signals','Signals']];
export function CommandBrain({tasks,notifications,employees,departments=[],founderId=null,selectedId=null,onSelect,governance,onAppoint,canGovern}) {
 const [choices,setChoices]=useState({});
 const [highlight,setHighlight]=useState(null);
 const [neuronFilter,setNeuronFilter]=useState('all');
 // Polling returns new arrays every few seconds; keep the same network object
 // (and so skip a WebGL redraw) unless the derived records actually changed.
 const derived=brainNetwork({employees,departments,tasks,notifications,founderId});
 const signature=JSON.stringify(derived);
 const network=useMemo(()=>derived,[signature]);
 const neuronById=new Map(network.nodes.map(n=>[n.id,n]));
 const neurons=network.nodes.filter(n=>neuronFilter==='all'||(neuronFilter==='working'&&n.running)
   ||(neuronFilter==='waiting'&&!n.running&&n.waiting)||(neuronFilter==='signals'&&n.signals>0));
 const [rotation,setRotation]=useState(0);
 const [pitch,setPitch]=useState(0),[zoom,setZoom]=useState(1),[autoRotate,setAutoRotate]=useState(true),[resetSignal,setResetSignal]=useState(0);
 const preset=(yaw,tilt)=>{setRotation(yaw);setPitch(tilt);setAutoRotate(false);};
 const [gpuReady,setGpuReady]=useState(false);
 const updateGpuReady=useCallback(ready=>setGpuReady(ready),[]);
 const known=Array.isArray(tasks);
 const active=known?tasks.filter(t=>t.status==='running'):[];
 const queued=known?tasks.filter(t=>['proposed','ready','waiting_approval'].includes(t.status)):[];
 const finished=known?tasks.filter(t=>['completed','passed'].includes(t.status)):[];
 const events=notifications?.recent||[];
 const assigned=known?[...active,...queued].slice(0,8):[];
 const employeeNames=new Map(employees.map(e=>[e.id,e.name]));
 const approved=(governance?.board||[]).map(s=>({...s,member_id:s.employee_id,approved:true}));
 const seats=boardFunctionSeats(employees,approved);
 const assignedToOtherSeat=new Set((governance?.board||[]).map(a=>a.employee_id));
 const openBoardCount=seats.filter(s=>!s.member).length;
 return <div className="command-overview">
   <div className="command-head"><div><small className="command-eyebrow">AGO · LIVE WORKFORCE OBSERVATORY</small><h2>AI Company Command Center</h2><p>Task assignment, governed activity and delivery evidence — not a simulated AI workforce.</p></div>
     <div className="command-metrics"><span><b>{known?tasks.length:'—'}</b>Tasks</span><span><b>{known?active.length:'—'}</b>Working</span><span><b>{known?queued.length:'—'}</b>Awaiting</span><span><b>{known?finished.length:'—'}</b>Finished</span></div>
   </div>
   <div className="brain-stage">
     <section className="brain-activity" aria-label="Communication and work signals"><h3>Communication &amp; work signals</h3><p className="brain-sub">Durable task events · never invented thoughts</p>
       <ol>
         {events.length?events.slice(0,7).map(e=>{const name=employeeNames.get(e.employee_id),tone=neuronById.get(e.employee_id)?.tone||'unknown';return <li key={e.id}>
           {name?<button type="button" className="brain-signal" aria-label={'Show '+name+' in the company brain: '+(e.body||'work event')}
             onMouseEnter={()=>setHighlight(e.employee_id)} onMouseLeave={()=>setHighlight(null)}
             onFocus={()=>setHighlight(e.employee_id)} onBlur={()=>setHighlight(null)}
             onClick={()=>onSelect(e.employee_id)}>
             <span className={'brain-dot tone-'+tone}/><span><strong>{brief(name,28)}</strong><small>{brief(e.body)}</small><time dateTime={e.created_at}>{ago(e.created_at)}</time></span>
           </button>:<div className="brain-signal static"><span className="brain-dot"/><span><strong>Work event #{e.id}</strong><small>{brief(e.body)}</small></span></div>}
         </li>;}):<li><div className="brain-signal static"><span className="brain-dot dormant"/><span><strong>{notifications?'Awaiting task transitions':'Event feed unavailable'}</strong><small>Recorded task events will appear here.</small></span></div></li>}
       </ol>
     </section>
     <div className="brain-hologram" aria-label="Interactive founder-controlled 3D work observatory">
       <ul className="brain-legend" aria-label="Company brain legend">
         <li><i className="tone-busy"/>Running task</li><li><i className="tone-waiting"/>Awaiting action</li>
         <li><i className="tone-idle"/>Idle</li><li><i className="tone-blocked"/>Blocked</li><li><i className="tone-failed"/>Failure recorded</li>
         <li><i className="route"/>Recorded route</li><li><i className="ring"/>Work signal</li>
       </ul>
       <div className={'brain-volume '+(active.length?'brain-volume-active':'')+(gpuReady?' webgl-active':'')}
         role="img" aria-label={'Layered 3D company work brain: '+active.length+' verified running tasks, '+queued.length+' awaiting action; not a simulated conscious AI'}
         style={{'--brain-rotation':rotation+'deg'}}>
        <Brain3DScene network={network} running={active.length} rotation={rotation} pitch={pitch} zoom={zoom} autoRotate={autoRotate} resetSignal={resetSignal} onZoom={setZoom}
          selectedId={selectedId} highlightId={highlight} onPick={id=>onSelect(id)} onReady={updateGpuReady}/>
        <div className="brain-depth-stack" aria-hidden="true">
          {CORTEX_DEPTHS.map((depth,index)=><svg key={depth} viewBox="0 0 420 300" className="brain-depth-slice"
            style={{'--cortex-depth':depth+'px','--cortex-scale':String(1-Math.abs(depth-30)/800)}}>
            <path d={CORTEX_CONTOUR} fill={index%2===0?'#18458d':'#16295e'}
              fillOpacity=".27" stroke={active.length?'#fa568c':'#66c4ff'}
              strokeOpacity={String(.23+index*.045)} strokeWidth="2.5"/>
          </svg>)}
        </div>
        <svg viewBox="0 0 420 300" className="brain-svg" aria-hidden="true">
        <defs><radialGradient id="agoBrainFill" cx=".44" cy=".35" r=".78"><stop stopColor="#335bd0" stopOpacity=".93"/><stop offset=".57" stopColor="#1e347d" stopOpacity=".8"/><stop offset="1" stopColor="#070c29"/></radialGradient>
          <linearGradient id="agoBrainStroke" x1="0" x2="1"><stop stopColor="#69ecff"/><stop offset=".48" stopColor="#ab83ff"/><stop offset="1" stopColor="#fa518e"/></linearGradient>
          <filter id="agoBrainGlow"><feGaussianBlur stdDeviation="4" result="blur"/><feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
        </defs>
        <path d="M199 247 C176 258 137 238 136 209 C93 205 82 164 110 139 C84 107 107 74 143 80 C149 44 194 39 207 65 C229 36 270 47 284 73 C323 62 347 92 337 119 C373 148 351 188 320 197 C323 228 293 251 266 239 C249 259 222 255 208 241Z" fill="url(#agoBrainFill)" stroke="url(#agoBrainStroke)" strokeWidth="3" filter="url(#agoBrainGlow)"/>
        <g fill="none" stroke="url(#agoBrainStroke)" strokeWidth="2.3" opacity=".95">
          <path d="M205 66 Q182 89 197 111 T184 164 Q215 196 198 242"/>
          <path d="M142 81 Q156 110 129 135 T146 178 T138 208"/>
          <path d="M284 74 Q270 110 302 120 T311 166 T321 195"/>
          <path d="M110 139 Q152 134 162 151 Q175 178 201 165"/>
          <path d="M338 119 Q294 138 275 151 Q245 163 231 145"/>
          <path d="M158 89 Q185 103 163 126 Q146 145 168 169 Q149 195 179 225"/>
          <path d="M251 59 Q224 84 254 106 Q271 128 248 147 T266 195 Q246 218 267 240"/>
          <path d="M139 201 Q177 197 197 213 T244 216 T319 196"/>
          <path d="M126 117 Q172 102 207 121 T288 106 T340 130"/>
          <path d="M205 70 Q215 115 207 158 Q225 204 207 242"/>
        </g>
        <g className="brain-cortex-nodes">{CORTEX_POINTS.map(([cx,cy],index)=>
          <circle key={index} cx={cx} cy={cy} r={index<active.length?5:3}
            className={index<active.length?'brain-node-working':'brain-node-idle'}
            data-verified-running={index<active.length?'true':'false'}/>
        )}</g>
        <path d="M209 244 Q216 265 202 281 M228 243 Q234 265 225 282" fill="none" stroke="#64cffa" strokeWidth="6" opacity=".8"/>
        </svg>
       </div>
       {gpuReady&&<p className="brain-hint">Drag to rotate · Shift/right-drag to move · Scroll, pinch or double-click to zoom</p>}
       <div className="brain-rotate-controls" role="group" aria-label="Rotate work brain">
         <button type="button" aria-label="Rotate brain left" onClick={()=>{setAutoRotate(false);setRotation(x=>x-15);}}>↶</button>
         <button type="button" aria-label="Reset brain rotation" onClick={()=>{preset(0,0);setZoom(1);setResetSignal(v=>v+1);}}>Reset view</button>
         <button type="button" aria-label="Show brain from the side" onClick={()=>preset(-55,-12)}>Side</button>
         <button type="button" aria-label="Show brain from above" onClick={()=>preset(36,48)}>Top</button>
         <button type="button" aria-label="Rotate brain right" onClick={()=>{setAutoRotate(false);setRotation(x=>x+15);}}>↷</button>
         <span className="brain-control-divider" aria-hidden="true"/>
         <button type="button" aria-label="Zoom brain out" disabled={zoom<=BRAIN_ZOOM.min} onClick={()=>setZoom(z=>Math.max(BRAIN_ZOOM.min,+(z/1.25).toFixed(3)))}>−</button>
         <button type="button" aria-label="Zoom brain in" disabled={zoom>=BRAIN_ZOOM.max} onClick={()=>setZoom(z=>Math.min(BRAIN_ZOOM.max,+(z*1.25).toFixed(3)))}>+</button>
         <button type="button" aria-pressed={autoRotate} aria-label="Auto-rotate brain" title="Turns only when reduced motion is off" onClick={()=>setAutoRotate(v=>!v)}>⟳ Auto</button>
       </div>
       <div className="brain-running"><span className={'brain-led '+(known?'connected':'')}/>{known?(active.length?'Recorded work is running · '+active.length+' active':queued.length?'Awaiting authorization / worker action':'Monitoring task records'):'Waiting for activity API'}</div>
     </div>
     <section className="brain-stats"><h3>Brain activity & delivery</h3><p className="brain-sub">Actual stored task states</p>
      <div className="brain-stat"><small>Employees working</small><b>{new Set(active.map(t=>t.assignee_id)).size}</b></div>
      <div className="brain-stat"><small>Pending action / approval</small><b>{known?queued.length:'—'}</b></div>
      <div className="brain-stat"><small>Red routes (recorded links)</small><b>{known?network.counts.routes:'—'}</b></div>
      <div className="brain-stat"><small>Recent durable work events</small><b>{notifications?events.length:'—'}</b></div>
      <section className="brain-work-detail" aria-label="Recorded company task assignments">
        <h4>Live assignment evidence</h4>
        {assigned.length?<ul>{assigned.map(task=><li key={task.id}>
          <span className={'brain-work-state '+(task.status==='running'?'work-running':'work-waiting')}>
            {task.status==='running'?'Running':task.status==='ready'?'Ready':task.status==='proposed'?'Proposed':'Approval required'}
          </span>
          <strong title={task.project_name||'Unlinked task'}>{brief(task.project_name||'Unlinked task',52)}</strong>
          {employeeNames.has(task.assignee_id)?
            <button type="button" onClick={()=>onSelect(task.assignee_id)}
              aria-label={'Open '+employeeNames.get(task.assignee_id)+' work details'}>
              {brief(employeeNames.get(task.assignee_id),26)} ↗
            </button>:<small>Employee not available</small>}
        </li>)}</ul>:<p>{known?'No running or queued assignments':'Task feed unavailable'}</p>}
      </section>
      <p className="brain-disclaimer">Visual monitor stays visible. A live model is only active when a configured, authorized runtime actually executes a job.</p>
     </section>
   </div>
   <details className="brain-directory">
    <summary>Company neurons · {network.nodes.length} employees · {network.counts.running} working · {network.counts.waiting} waiting</summary>
    <div className="brain-directory-filters" role="group" aria-label="Filter company neurons">
     {NEURON_FILTERS.map(([key,label])=><button key={key} type="button" aria-pressed={neuronFilter===key} onClick={()=>setNeuronFilter(key)}>{label}</button>)}
    </div>
    {neurons.length?<ul aria-label="Company neurons">{neurons.map(n=><li key={n.id}>
      <button type="button" data-neuron={n.id} data-tone={n.tone} aria-current={n.id===selectedId?'true':undefined}
        onMouseEnter={()=>setHighlight(n.id)} onMouseLeave={()=>setHighlight(null)}
        onFocus={()=>setHighlight(n.id)} onBlur={()=>setHighlight(null)} onClick={()=>onSelect(n.id)}
        aria-label={n.name+', '+n.department+': '+n.label+(n.routed?', on a recorded task route':'')+(n.signals?', '+n.signals+' work signals':'')}>
        <i className={'tone-'+n.tone}/><strong>{brief(n.name,30)}</strong><small>{n.department}</small>
        <span>{n.label}{n.signals?' · '+n.signals+' signal'+(n.signals===1?'':'s'):''}</span>
      </button></li>)}</ul>:<p>No employees match this filter.</p>}
   </details>
   <section className="board-command" aria-label="Board governance functions">
    <div><h3>Board of Directors</h3><small>{openBoardCount} of 5 seats unassigned · Software AI roles, not legal directors · Founder approval required</small></div>
    <div className="board-seats">{seats.map(s=>{
      const options=employees.filter(e=>e.kind==='ai'&&(!assignedToOtherSeat.has(e.id)||e.id===s.member?.id));
      const selected=choices[s.title]||s.member?.id||'';
      return <div key={s.title} className="board-seat">
        <strong>{BOARD_TITLES[s.title]}</strong>
        <small>{s.member?'Appointed: '+s.member.name:'Vacant · AI appointment required'}</small>
        <span><b>{s.title}</b> · {s.responsibility}</span>
        {s.member&&<button type="button" className="board-detail" onClick={()=>onSelect(s.member.id)}>View officer profile</button>}
        {canGovern&&<div className="board-appoint">
          <select aria-label={'Appoint AI '+BOARD_TITLES[s.title]} value={selected} disabled={Boolean(s.member)}
            onChange={e=>setChoices(old=>({...old,[s.title]:e.target.value}))}>
             <option value="">Select eligible AI employee</option>
             {options.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button type="button" disabled={Boolean(s.member)||!selected}
            onClick={()=>onAppoint(s.title,selected)}>{s.member?'Seat appointed':'Appoint AI officer'}</button>
          {!s.member&&!options.length&&<small>No eligible AI employee found. Add or explicitly assign a suitable AI role first.</small>}
        </div>}
      </div>;
    })}</div>
   </section>
 </div>;
}
