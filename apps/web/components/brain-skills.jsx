"use client";
import {useCallback,useEffect,useMemo,useState} from 'react';
import {areaName,brainStats,brainView,filterSkills,learnText,usageText} from './brain-skills-state';

const BASE='/v1/organization/company/brain/skills';

/** Company Brain: the skills every AI employee works with. Founder-only.
 * Skills are guidance only; nothing here approves or runs work. */
export function BrainSkills({api,me,active=true}){
 const founder=Boolean(me?.roles?.includes('founder'));
 const [view,setView]=useState(null),[error,setError]=useState(''),[notice,setNotice]=useState('');
 const [query,setQuery]=useState(''),[area,setArea]=useState('all'),[showRetired,setShowRetired]=useState(false);
 const [topic,setTopic]=useState(''),[busy,setBusy]=useState('');
 const apply=useCallback(raw=>{const next=brainView(raw);if(!next)throw new Error('The Brain could not be read. Press Refresh.');setView(next);},[]);
 const load=useCallback(()=>api.request(BASE).then(apply),[api,apply]);
 useEffect(()=>{
  if(!founder||!active)return undefined;
  let live=true;
  load().then(()=>{if(live)setError('');}).catch(e=>{if(live)setError(e?.message||'The Brain is unavailable right now.');});
  return()=>{live=false;};
 },[founder,active,load]);
 const shown=useMemo(()=>filterSkills(view?.skills,{query,area,showRetired}),[view,query,area,showRetired]);
 if(!founder)return <div className="brain-skills"><h2>Company Brain</h2><p>Only the Founder manages the Brain's skills.</p></div>;
 async function act(label,work,done){
  setBusy(label);setError('');setNotice('');
  try{const result=await work();if(done)await done(result);}
  catch(e){setError(e?.message||'That did not work.');}
  finally{setBusy('');}
 }
 const learn=body=>act('learn',()=>api.request(BASE+'/learn',{method:'POST',body,timeoutMs:150000}),
  async r=>{setNotice(learnText(r));setTopic('');await load();});
 const toggle=(skill)=>act(skill.ref,()=>api.request(BASE+(skill.retired?'/restore':'/retire'),{method:'POST',body:{ref:skill.ref}}),
  r=>{apply(r);setNotice((skill.retired?'Restored: ':'Retired: ')+skill.title+'.');});
 const stats=brainStats(view);
 return <div className="brain-skills">
  <header className="brain-head">
   <div><h2>Company Brain</h2>
    <p>Every AI employee gets the best matching skill for its work, inside its prompt. Skills are guidance only: they never approve or run anything.</p></div>
  </header>
  {error&&<p role="alert" className="brain-error">{error}</p>}
  {notice&&<p role="status" className="brain-notice">{notice}</p>}
  {busy==='learn'&&<p role="status" className="brain-notice">STARK is drafting the skill and JARVIS is deciding. This can take a minute or two…</p>}
  {view&&<>
   <div className="brain-stats" role="list" aria-label="Brain at a glance">
    <div role="listitem"><b>{stats.active}</b><span>skills in use</span></div>
    <div role="listitem"><b>{stats.areas}</b><span>areas of work</span></div>
    <div role="listitem"><b>{stats.learned}</b><span>learned by the company</span></div>
    <div role="listitem"><b>{stats.used}</b><span>times given to AI work</span></div>
   </div>

   <section className="brain-teach" aria-labelledby="brain-teach-title">
    <h3 id="brain-teach-title">Teach the Brain a new skill</h3>
    <p>STARK (CTO seat) drafts it; JARVIS (AI CEO) approves or refuses it. Approved skills go to every matching task.</p>
    <form onSubmit={e=>{e.preventDefault();if(topic.trim().length>=3)learn({topic:topic.trim()});}}>
     <label htmlFor="brain-topic">What should the Brain learn?</label>
     <textarea id="brain-topic" rows={2} maxLength={500} value={topic} disabled={busy!==''}
      placeholder="For example: how to apply for a GeM government tender, or how to edit a reel for Instagram"
      onChange={e=>setTopic(e.target.value)}/>
     <button type="submit" className="brain-primary" disabled={busy!==''||topic.trim().length<3}>{busy==='learn'?'Learning…':'Teach'}</button>
    </form>
   </section>

   {view.gaps.length>0&&<section className="brain-gaps" aria-labelledby="brain-gaps-title">
    <h3 id="brain-gaps-title">Work that found no skill ({view.gaps.length})</h3>
    <ul>{view.gaps.map(g=><li key={g.id}>
     <div><strong>{g.topic}</strong><small>{[g.stage,g.role].filter(Boolean).join(' · ')}</small></div>
     <button type="button" disabled={busy!==''} onClick={()=>learn({gap_id:g.id})} aria-label={'Learn a skill for: '+g.topic}>Learn this</button>
    </li>)}</ul>
   </section>}

   {view.decisions.length>0&&<section className="brain-decisions" aria-labelledby="brain-decisions-title">
    <h3 id="brain-decisions-title">AI CEO decisions</h3>
    <ul>{view.decisions.slice(0,8).map(d=><li key={d.id} className={d.status}>
     <span className={'brain-chip '+(d.status==='approved'?'ok':'bad')}>{d.status==='approved'?'Approved':'Refused'}</span>
     <div><strong>{d.title}</strong><small>{d.reviewed_by_name}: {d.review_text}</small></div>
    </li>)}</ul>
   </section>}

   <section className="brain-library" aria-labelledby="brain-library-title">
    <div className="brain-library-head"><h3 id="brain-library-title">Skills</h3>
     <label className="brain-search"><span className="sr-only">Search skills</span>
      <input type="search" value={query} placeholder="Search skills…" onChange={e=>setQuery(e.target.value)}/></label>
    </div>
    <div className="brain-areas" role="group" aria-label="Areas of work">
     <button type="button" aria-pressed={area==='all'} onClick={()=>setArea('all')}>All ({stats.active})</button>
     {Object.entries(view.domains).map(([d,n])=><button key={d} type="button" aria-pressed={area===d} onClick={()=>setArea(d)}>{areaName(d)} ({n})</button>)}
    </div>
    <label className="brain-retired"><input type="checkbox" checked={showRetired} onChange={e=>setShowRetired(e.target.checked)}/> Show retired skills</label>
    <p className="brain-count" aria-live="polite">{shown.length} {shown.length===1?'skill':'skills'}</p>
    <ul className="brain-list">{shown.map(s=><li key={s.ref} className={'brain-skill'+(s.retired?' retired':'')}>
     <details>
      <summary><strong>{s.title}</strong><span className="brain-area">{areaName(s.domain)}</span>
       {!s.builtin&&<span className="brain-chip ok">Learned</span>}{s.retired&&<span className="brain-chip">Retired</span>}
       <small>{usageText(s.usage)}</small></summary>
      <p className="brain-body">{s.body}</p>
      <p className="brain-meta">For: {s.roles.join(', ')} · Stages: {s.stages.join(', ')} · Source: {s.source}</p>
      <button type="button" disabled={busy!==''} onClick={()=>toggle(s)} aria-label={(s.retired?'Restore ':'Retire ')+s.title}>{s.retired?'Restore':'Retire'}</button>
     </details>
    </li>)}</ul>
   </section>
  </>}
 </div>;
}
