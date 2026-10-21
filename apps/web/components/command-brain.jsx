"use client";
import {useState} from 'react';
import {boardFunctionSeats} from '@ago/sdk/company';

const brief=(text,max=110)=>text?.length>max?text.slice(0,max)+'…':text;
export function CommandBrain({tasks,notifications,employees,onSelect,governance,onAppoint,canGovern}) {
 const [choices,setChoices]=useState({});
 const [rotation,setRotation]=useState(0);
 const known=Array.isArray(tasks);
 const active=known?tasks.filter(t=>t.status==='running'):[];
 const queued=known?tasks.filter(t=>['proposed','ready','waiting_approval'].includes(t.status)):[];
 const finished=known?tasks.filter(t=>['completed','passed'].includes(t.status)):[];
 const events=notifications?.recent||[];
 const approved=(governance?.board||[]).map(s=>({...s,member_id:s.employee_id,approved:true}));
 const seats=boardFunctionSeats(employees,approved);
 return <div className="command-overview">
   <div className="command-head"><div><small className="command-eyebrow">AGO · LIVE WORKFORCE OBSERVATORY</small><h2>AI Company Command Center</h2><p>Task assignment, governed activity and delivery evidence — not a simulated AI workforce.</p></div>
     <div className="command-metrics"><span><b>{known?tasks.length:'—'}</b>Tasks</span><span><b>{known?active.length:'—'}</b>Working</span><span><b>{known?queued.length:'—'}</b>Awaiting</span><span><b>{known?finished.length:'—'}</b>Finished</span></div>
   </div>
   <div className="brain-stage">
     <section className="brain-activity"><h3>◉ What the Brain Is Tracking</h3><p className="brain-sub">Recorded events, never invented thoughts</p>
       <ol>
         {events.length?events.slice(0,6).map(e=><li key={e.id}><span className="brain-dot"/><div><strong>Work event #{e.id}</strong><small>{brief(e.body)}</small></div></li>):<li><span className="brain-dot dormant"/><div><strong>{notifications?'Awaiting task transitions':'Event feed unavailable'}</strong><small>Recorded task events will appear here.</small></div></li>}
       </ol>
     </section>
     <div className="brain-hologram" aria-label="Interactive founder-controlled 3D work observatory">
       <div className="brain-orbit orbit-one"/><div className="brain-orbit orbit-two"/>
       <div className={'brain-volume '+(active.length?'brain-volume-active':'')}
         role="img" aria-label={'3D-style rotating company work brain: '+active.length+' verified running tasks, '+queued.length+' awaiting action; not a simulated conscious AI'}
         style={{'--brain-rotation':rotation+'deg'}}>
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
        <g fill="#f99cff" filter="url(#agoBrainGlow)"><circle cx="162" cy="126" r="5"/><circle cx="254" cy="106" r="5"/><circle cx="205" cy="162" r="5"/><circle cx="269" cy="197" r="5"/><circle cx="147" cy="201" r="4"/><circle cx="295" cy="137" r="4"/></g>
        <path d="M209 244 Q216 265 202 281 M228 243 Q234 265 225 282" fill="none" stroke="#64cffa" strokeWidth="6" opacity=".8"/>
        </svg>
       </div>
       <div className="brain-rotate-controls" aria-label="Rotate work brain">
         <button type="button" aria-label="Rotate brain left" onClick={()=>setRotation(x=>Math.max(-68,x-15))}>↶</button>
         <button type="button" aria-label="Reset brain rotation" onClick={()=>setRotation(0)}>Front view</button>
         <button type="button" aria-label="Rotate brain right" onClick={()=>setRotation(x=>Math.min(68,x+15))}>↷</button>
       </div>
       <div className="brain-label label-analyze">Analyze</div><div className="brain-label label-plan">Plan</div><div className="brain-label label-delegate">Delegate</div><div className="brain-label label-review">Review</div>
       <div className="brain-running"><span className={'brain-led '+(known?'connected':'')}/>{known?(active.length?'Recorded work is running · '+active.length+' active':queued.length?'Awaiting authorization / worker action':'Monitoring task records'):'Waiting for activity API'}</div>
     </div>
     <section className="brain-stats"><h3>Brain activity & delivery</h3><p className="brain-sub">Actual stored task states</p>
      <div className="brain-stat"><small>Employees working</small><b>{new Set(active.map(t=>t.assignee_id)).size}</b></div>
      <div className="brain-stat"><small>Pending action / approval</small><b>{known?queued.length:'—'}</b></div>
      <div className="brain-stat"><small>Recent durable work events</small><b>{notifications?events.length:'—'}</b></div>
      <p className="brain-disclaimer">Visual monitor stays visible. A live model is only active when a configured, authorized runtime actually executes a job.</p>
     </section>
   </div>
   <section className="board-command" aria-label="Board governance functions">
    <div><h3>Board of Directors</h3><small>Strategic governance · seats are unassigned until explicitly appointed</small></div>
    <div className="board-seats">{seats.map(s=><div key={s.title} className="board-seat">
        <strong>{s.title}</strong><small>{s.member?s.member.name:'Not appointed'}</small>
        <span>{s.responsibility}</span>
        {s.member&&<button type="button" className="board-detail" onClick={()=>onSelect(s.member.id)}>View member ↗</button>}
        {canGovern&&<div className="board-appoint">
          <select aria-label={'Appoint '+s.title} value={choices[s.title]||s.member?.id||''} onChange={e=>setChoices(old=>({...old,[s.title]:e.target.value}))}>
             <option value="">Select employee</option>{employees.map(e=><option key={e.id} value={e.id}>{e.name}</option>)}
          </select>
          <button type="button" disabled={!(choices[s.title]||s.member?.id)} onClick={()=>onAppoint(s.title,choices[s.title]||s.member?.id)}>Approve seat</button>
        </div>}
       </div>)}</div>
   </section>
 </div>;
}
