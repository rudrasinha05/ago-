"use client";
import {useEffect,useRef,useState} from 'react';

const BASE='/v1/organization/company';
const KIND_LABELS={status:'Task status',report:'Report',staffing:'Staffing',github:'GitHub',qa:'QA',docs:'Documents',project:'Project'};
const when=value=>{
  const at=Date.parse(value);if(!Number.isFinite(at))return '';
  const seconds=Math.max(0,Math.round((Date.now()-at)/1000));
  if(seconds<60)return 'just now';if(seconds<3600)return Math.round(seconds/60)+' min ago';
  if(seconds<86400)return Math.round(seconds/3600)+' h ago';return new Date(at).toLocaleString();
};

/** Merge an incremental notification page into the durable list shown so far.
 * The API returns newest-first on boot and ascending `after_id` pages later;
 * counts in a page are authoritative, recent events accumulate (deduped). */
export function mergeNotificationPage(previous,next,limit=200){
  if(!next)return previous;
  if(!previous)return {...next,recent:[...(next.recent||[])].sort((a,b)=>b.id-a.id).slice(0,limit)};
  const byId=new Map([...(previous.recent||[]),...(next.recent||[])].map(e=>[e.id,e]));
  return {...previous,...next,recent:[...byId.values()].sort((a,b)=>b.id-a.id).slice(0,limit)};
}

/** Unread state exists only when the server provides a per-reader cursor. */
export function readState(data){
  const supported=Number.isInteger(data?.read_through_id);
  if(!supported)return {supported:false,unread:null,isUnread:()=>false};
  const unread=Number.isInteger(data.unread_count)?data.unread_count
    :(data.recent||[]).filter(e=>e.id>data.read_through_id).length;
  return {supported:true,unread,isUnread:event=>event.id>data.read_through_id};
}

export function CompanyNotificationCenter({api,data,employees,onSelect,onRead}){
  const [open,setOpen]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const panel=useRef(null),toggle=useRef(null);
  const names=new Map(employees.map(e=>[e.id,e.name]));
  const state=readState(data);
  const events=data?.recent||[];
  const newest=events.reduce((max,e)=>Math.max(max,e.id),0);
  useEffect(()=>{
    if(!open)return;
    const onKey=event=>{if(event.key==='Escape'){setOpen(false);toggle.current?.focus();}};
    const onDown=event=>{if(!panel.current?.contains(event.target)&&!toggle.current?.contains(event.target))setOpen(false);};
    document.addEventListener('keydown',onKey);document.addEventListener('pointerdown',onDown);
    return()=>{document.removeEventListener('keydown',onKey);document.removeEventListener('pointerdown',onDown);};
  },[open]);
  async function markRead(){
    setBusy(true);setError('');
    try{
      const result=await api.request(BASE+'/notifications/read',{method:'POST',body:{through_id:newest}});
      onRead?.(result);
    }catch(e){setError(e.message||'Could not record read state.');}
    finally{setBusy(false);}
  }
  const badge=state.supported&&state.unread>0?(state.unread>99?'99+':String(state.unread)):null;
  const label=!data?'Work notifications unavailable'
    :state.supported?`Work notifications, ${state.unread} unread`:`Work notifications, ${events.length} recorded events`;
  return <div className="notification-center">
    <button ref={toggle} type="button" className="notification-toggle" aria-label={label}
      aria-expanded={open} aria-controls="ago-notification-panel" onClick={()=>setOpen(v=>!v)} disabled={!data}>
      <svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path fill="currentColor" d="M12 22a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 12 22Zm7-6V11a7 7 0 0 0-5.5-6.84V3.5a1.5 1.5 0 0 0-3 0v.66A7 7 0 0 0 5 11v5l-1.7 1.7A1 1 0 0 0 4 19.4h16a1 1 0 0 0 .7-1.7Z"/></svg>
      <span>Notifications</span>
      {badge&&<b className="notification-badge" aria-hidden="true">{badge}</b>}
    </button>
    {open&&<section id="ago-notification-panel" ref={panel} className="notification-panel" aria-label="Work notifications">
      <header>
        <div><h2>Work notifications</h2>
          <p>{state.supported?`${state.unread} unread · durable per-user read state`
            :'Recorded task events. Unread tracking is unavailable until the server provides a read cursor.'}</p></div>
        {state.supported&&<button type="button" className="btn" disabled={busy||!state.unread||!newest} onClick={markRead}>
          {busy?'Saving…':'Mark all read'}</button>}
      </header>
      {error&&<p className="notification-error" role="alert">{error}</p>}
      {events.length?<ol>{events.slice(0,50).map(event=>{
        const name=names.get(event.employee_id),unread=state.isUnread(event);
        return <li key={event.id} className={unread?'unread':''}>
          <button type="button" disabled={!name} onClick={()=>{onSelect?.(event.employee_id);setOpen(false);}}
            aria-label={(unread?'Unread: ':'')+(name||'Unavailable employee')+' — '+(event.body||'work event')}>
            <span className={'notification-kind kind-'+(event.kind||'status')}>{KIND_LABELS[event.kind]||'Work event'}</span>
            <strong>{name||'Employee not visible'}</strong>
            <span className="notification-body">{event.body}</span>
            <time dateTime={event.created_at}>{when(event.created_at)} · #{event.id}</time>
          </button>
        </li>;})}</ol>
      :<p className="notification-empty">No recorded work events yet.</p>}
    </section>}
  </div>;
}
