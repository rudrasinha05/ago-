"use client";
import Link from 'next/link';
import {useRouter} from 'next/navigation';
import {useCallback,useEffect,useRef,useState} from 'react';
import {resource,validateProfile} from '@ago/sdk/session';
import {loadWorkspace,twinDefaults} from '@ago/sdk/workspace';
import {PAGES,renderPage} from '@ago/ui/compat/views';
import {handleAction} from '@ago/ui/compat/actions';
import {sprite} from '@ago/ui/sprite';
import {Button,Loading,Notice} from '@ago/ui/components';
import {Dashboard} from './dashboard';
import {useSession} from './session';
export function Workspace({page}) {
  const {api,me,logout,epoch}=useSession(); const router=useRouter();
  const [data,setData]=useState(null), [revision,setRevision]=useState(0), [toast,setToast]=useState(''), [open,setOpen]=useState(false);
  const state=useRef({page,me,data:{},twin:{}}), sequence=useRef(0), dialog=useRef(null), screen=useRef(null), active=useRef(false), timer=useRef(null);
  state.current.page=page;state.current.me=me;
  const notify=useCallback(message=>{if(!active.current)return;setToast(message);clearTimeout(timer.current);timer.current=setTimeout(()=>setToast(''),5500);},[]);
  const refresh=useCallback(async()=>{
    const version=++sequence.current, session=epoch.current;setData(null);
    const result=await loadWorkspace(api,page);
    if(!active.current || sequence.current!==version || epoch.current!==session)return;
    state.current.data=result;
    if(page==='twin')state.current.twin=twinDefaults(result);
    setData(result);setRevision(x=>x+1);
  },[api,page,epoch]);
  useEffect(()=>{
    active.current=true;setOpen(false);dialog.current?.close();
    refresh().catch(()=>{if(active.current)setData({});});
    return ()=>{active.current=false;sequence.current++;clearTimeout(timer.current);dialog.current?.close();};
  },[refresh]);
  useEffect(()=>{if(data!==null)screen.current?.focus({preventScroll:true});},[page,data]);
  useEffect(()=>{
    const host=screen.current?.querySelector('.workspace-view');
    if(!host)return;
    // Compatibility controls are unmanaged DOM: native events bridge into React state.
    const update=event=>{
      const target=event.target, key=target.dataset.twinField;
      if(key){try{
        const hadSimulation=Boolean(state.current.twin.simulation);
        state.current.twin.profile=validateProfile({...state.current.twin.profile,[key]:Number(target.value)});
        state.current.twin.simulation=null;
        const output=host.querySelector('#output-'+key);
        if(output)output.textContent=String(target.value)+(key==='backlog_limit'?' tasks':'%');
        if(hadSimulation)setRevision(x=>x+1);
      }catch(e){notify(e.message);}}
      if(target.id==='snapshot-select'&&event.type==='change'){
        state.current.twin.snapshotId=target.value;state.current.twin.simulation=null;setRevision(x=>x+1);
      }
    };
    host.addEventListener('input',update);host.addEventListener('change',update);
    return ()=>{host.removeEventListener('input',update);host.removeEventListener('change',update);};
  },[data,revision,page,notify]);
  if(!me)return null;
  async function action(event) {
    const button=event.target.closest('button[data-action]');if(!button)return;
    const version=sequence.current, session=epoch.current;
    const valid=()=>active.current&&sequence.current===version&&epoch.current===session;
    const scoped={request:async(...args)=>{if(!valid())throw new Error('This workspace changed.');const result=await api.request(...args);if(!valid())throw new Error('This workspace changed.');return result;}};
    const ctx={api:scoped,state:state.current,can:p=>me.permissions.includes(p),dialog:dialog.current,
      refreshCurrent:()=>valid()?refresh():undefined,goPage:key=>{if(valid())router.push(key==='overview'?'/':'/'+key+'/');},
      showPage:()=>{if(valid())setRevision(x=>x+1);},toast:message=>{if(valid())notify(message);}};
    button.disabled=true;
    try {await handleAction(button.dataset.action,button.dataset.id,ctx);}
    catch(e){if(valid())notify(e.message || 'Action unavailable.');}
    finally{if(button.isConnected)button.disabled=false;}
  }
  return <div id="workspace" className="next-workspace">
    <div dangerouslySetInnerHTML={{__html:sprite}} />
    <header className="workspace-header"><Link href="/" className="brand">AGO <span>Workspace</span></Link><p>{me.display_name}<span className="member-role">{me.roles?.join(' · ')}</span></p><Button onClick={()=>setOpen(x=>!x)} aria-expanded={open} aria-controls="primary-nav" className="btn nav-toggle">Menu</Button><Button onClick={logout}>Sign out</Button></header>
    <div className="workspace-body"><nav id="primary-nav" className={open?'workspace-nav open':'workspace-nav'} aria-label="Workspaces">{Object.entries(PAGES).map(([key,value])=><Link key={key} href={key==='overview'?'/':'/'+key+'/'} aria-current={page===key?'page':undefined} onClick={()=>setOpen(false)}>{value.title}</Link>)}<a href="/console/">Control Center</a></nav>
      <main id="screen" ref={screen} tabIndex={-1} className="screen">
        <div className="workspace-toolbar"><p className="muted">{PAGES[page].title} · Your organization</p><Button onClick={()=>refresh().catch(()=>notify('Unable to refresh.'))} disabled={data===null}>Refresh</Button></div>
        {data===null?<Loading />:<><div key={revision} className="workspace-view" onClick={action} dangerouslySetInnerHTML={{__html:renderPage(page,state.current.data,state.current)}} />{page==='overview'&&<Dashboard key={me.id} api={api} me={me} data={data}/>}</>}
      </main>
    </div>
    <dialog id="action-dialog" ref={dialog} aria-labelledby="dialog-title" onClick={e=>{if(e.target===dialog.current)dialog.current.close();}}><div id="dialog-content" className="dialog-content" /></dialog>
    <div className="workspace-announcement" aria-live="polite" aria-atomic="true">{toast&&<Notice>{toast}</Notice>}</div>
  </div>;
}
