"use client";
import {useEffect,useRef,useState} from 'react';
import styles from './development-workspace.module.css';

const reviews='/v1/agents/workspace-reviews/';
const send=(body,method='POST')=>({method,body,timeoutMs:240000});
const revisionOf=({revision,run_id,candidate_sha256})=>({revision,run_id,candidate_sha256});
const uid=()=>crypto.randomUUID();
function Highlight({value}){
 const tokens=value.split(/(#[^\n]*|\/\/[^\n]*|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\b(?:class|def|return|if|else|elif|from|import|for|while|try|except|assert|const|let|function|export|await|async|new|throw|true|false|None|True|False|\d+)\b)/g);
 return tokens.map((token,i)=>i%2?<span key={i} className={token.startsWith('#')||token.startsWith('//')?styles.comment:/^["']/.test(token)?styles.str:styles.keyword}>{token}</span>:token);
}

export function DevelopmentWorkspace({api,project,stage}){
 const root='/v1/agents/projects/'+encodeURIComponent(project)+'/tasks/'+encodeURIComponent(stage.task_id)+'/workspace';
 const [open,setOpen]=useState(false),[snapshot,setSnapshot]=useState(null),[files,setFiles]=useState([]);
 const [path,setPath]=useState(''),[busy,setBusy]=useState(''),[error,setError]=useState('');
 const [runs,setRuns]=useState([]),[tests,setTests]=useState([]),[review,setReview]=useState('');
 const [reviewer,setReviewer]=useState(''),[target,setTarget]=useState(''),[sha,setSha]=useState('');
 const [message,setMessage]=useState(''),[operation,setOperation]=useState(null),[notice,setNotice]=useState('');
 const [newFile,setNewFile]=useState('');
 const paint=useRef(null),alive=useRef(false),lock=useRef(false);
 useEffect(()=>{alive.current=true;return ()=>{alive.current=false;};},[]);
 const current=files.find(f=>f.path===path);
 const dirty=snapshot&&JSON.stringify(snapshot.files)!==JSON.stringify(files);
 function install(data){setSnapshot(data);setFiles(data.files);setPath(p=>data.files.some(f=>f.path===p)?p:data.files[0]?.path||'');setOperation(null);}
 async function action(label,work){
  if(lock.current)return;
  lock.current=true;setBusy(label);setError('');setNotice('');
  try{await work();}catch(e){if(alive.current)setError(e.message||'Request failed');}
  finally{lock.current=false;if(alive.current)setBusy('');}
 }
 async function refresh(){
  const [r,t]=await Promise.all([api.request(root+'/terminal'),api.request(root+'/tests')]);
  if(alive.current){setRuns(r.attempts);setTests(t.attempts);}
 }
 useEffect(()=>{
  if(!open)return;
  let live=true,timer;
  async function poll(){try{const [r,t]=await Promise.all([api.request(root+'/terminal'),api.request(root+'/tests')]);
   if(live){setRuns(r.attempts);setTests(t.attempts);}
  }catch(e){if(live)setError(e.message);}finally{if(live)timer=setTimeout(poll,2500);}}
  poll();return ()=>{live=false;clearTimeout(timer);};
 },[open,api,root]);
 async function load(){const data=await api.request(root);if(alive.current){install(data);setOpen(true);}}
 const latest=tests.find(t=>snapshot&&t.revision===snapshot.revision&&t.candidate_sha256===snapshot.candidate_sha256);
 const disabled=!!busy||dirty;
 function patch(content){setFiles(items=>items.map(f=>f.path===path?{...f,content}:f));}
 if(!open)return <div><button type="button" disabled={!!busy} onClick={()=>action('Opening',load)}>Open development workspace</button>{error&&<p role="alert">{error}</p>}</div>;
 return <section className={styles.panel} aria-label="Development workspace"><header><h4>Development workspace</h4><span>Revision {snapshot.revision}</span></header>
 <div className={styles.grid}><div className={styles.files} role="group" aria-label="Project files">
 {files.map(f=><button type="button" key={f.path} aria-pressed={path===f.path} onClick={()=>setPath(f.path)}>{f.path}</button>)}</div>
 <div><strong>{path}</strong><div className={styles.editor}><pre ref={paint} aria-hidden="true"><Highlight value={(current?.content||'')+'\n'}/></pre>
 <textarea aria-label={'Edit '+path} spellCheck={false} wrap="off" value={current?.content||''} disabled={!!busy}
 onScroll={e=>{paint.current.scrollTop=e.target.scrollTop;paint.current.scrollLeft=e.target.scrollLeft;}} onChange={e=>patch(e.target.value)}/></div></div></div>
 <div className={styles.tools}><label>New file path <input value={newFile} placeholder="src/main.mjs" onChange={e=>setNewFile(e.target.value)}/></label>
 <button disabled={!!busy||!newFile.trim()||files.length>=6} onClick={()=>{const name=newFile.trim();if(files.some(f=>f.path===name)||name.split('/').some(part=>!part||part==='..')||!/^(src|tests|docs)\/[a-zA-Z0-9_./-]+$/.test(name)){setError('Choose a unique path under src, tests or docs.');return;}setFiles(items=>[...items,{path:name,content:''}]);setPath(name);setNewFile('');}}>Add file</button>
 <button disabled={!!busy||!current} onClick={()=>{if(window.confirm('Remove '+path+' from this draft?')){const remaining=files.filter(f=>f.path!==path);setFiles(remaining);setPath(remaining[0]?.path||'');}}}>Remove selected file</button>
 </div><div className={styles.tools}>
 <button disabled={!!busy||!dirty} onClick={()=>action('Saving',async()=>install(await api.request(root,send({files,expected_revision:snapshot.revision,run_id:snapshot.run_id},'PUT'))))}>Save revision</button>
 <button disabled={!!busy} onClick={()=>{if(!dirty||window.confirm('Discard unsaved edits and reload?'))action('Reloading',load);}}>Reload</button>
 <button disabled={disabled||!path.startsWith('src/')} onClick={()=>action('Running',async()=>{await api.request(root+'/terminal',send({...revisionOf(snapshot),attempt_id:uid(),entry:path}));await refresh();})}>Run selected file</button>
 <button disabled={disabled} onClick={()=>action('Testing',async()=>{await api.request(root+'/tests',send({...revisionOf(snapshot),attempt_id:uid()}));await refresh();})}>Run tests</button>
 {latest?.receipt?.status==='failed'&&<button disabled={disabled} onClick={()=>action('Repairing',async()=>{const r=await api.request(root+'/tests/'+latest.attempt_id+'/repair',send({}));install(r.workspace);await refresh();})}>Repair and retest</button>}</div>
 <p role="status">{busy||notice||(dirty?'Unsaved changes':'Saved revision '+snapshot.revision)}</p>{error&&<p role="alert">{error}</p>}
 <h5>Terminal</h5>{!runs.length&&<p>No commands recorded.</p>}
 {runs.map(r=><details key={r.attempt_id} open={r===runs[0]||undefined}><summary>{r.entry} · revision {r.revision} · {r.status}{r.exit_code!=null?' · exit '+r.exit_code:''}</summary>
 <pre className={styles.output}>{r.output}</pre>{r.status==='running'&&<button disabled={r.stop_requested} onClick={async()=>{try{await api.request(root+'/terminal/'+r.attempt_id+'/stop',send({}));await refresh();}catch(e){setError(e.message);}}}>Stop command</button>}</details>)}
 <h5>Test history</h5>{!tests.length&&<p>No test attempts recorded.</p>}{tests.map(t=><details key={t.attempt_id}><summary>Revision {t.revision} · {t.receipt?.status||'Awaiting result'}</summary><pre className={styles.output}>{JSON.stringify(t.receipt,null,2)}</pre></details>)}
 <details><summary>Independent QA and GitHub handoff</summary>
 <label>QA reviewer ID <input value={reviewer} onChange={e=>setReviewer(e.target.value.trim())}/></label>
 <button disabled={disabled||!reviewer||latest?.receipt?.status!=='passed'} onClick={()=>action('Requesting QA',async()=>{const r=await api.request(root+'/tests/'+latest.attempt_id+'/review/'+encodeURIComponent(reviewer),send({}));setReview(r.id);setNotice('QA requested. Share the review ID with the assigned reviewer.');})}>Request independent QA</button>
 <label>Review ID <input value={review} onChange={e=>{setReview(e.target.value.trim());setOperation(null);}}/></label>
 <label>Registered GitHub project ID <input value={target} onChange={e=>{setTarget(e.target.value.trim());setOperation(null);}}/></label>
 <label>Expected develop commit SHA <input value={sha} onChange={e=>{setSha(e.target.value.trim());setOperation(null);}}/></label>
 <label>Commit message <input value={message} onChange={e=>{setMessage(e.target.value);setOperation(null);}}/></label>
 <button disabled={disabled||!review||!target||!message||!/^[a-f0-9]{40}$/.test(sha)} onClick={()=>action('Preparing handoff',async()=>{
 const packet=await api.request(reviews+encodeURIComponent(review));
 if(packet.project_id!==project||packet.task_id!==stage.task_id||packet.candidate_sha256!==snapshot.candidate_sha256)throw new Error('Review belongs to a different workspace revision');
 const r=await api.request(reviews+encodeURIComponent(review)+'/github-handoff/'+encodeURIComponent(target)+'/'+uid(),send({expected_sha:sha,message}));setOperation(r.github_operation);})}>Prepare reviewed commit</button>
 {operation&&<button disabled={disabled} onClick={()=>action('Submitting proposal',async()=>{const r=await api.request('/v1/enterprise/reviews/integration');await api.request('/v1/enterprise/reviews/integration/propose',send({command:'github_operation',specification:operation,operation_key:'workspace:'+operation.id,base_revision:r.revision,rationale:'Workspace revision '+snapshot.revision+' passed independent QA '+review}));setNotice('Commit proposal submitted. Continue in GitHub delivery.');setOperation(null);})}>Submit for GitHub approval</button>}</details></section>;
}

export function WorkspaceReview({api}){
 const [id,setId]=useState(''),[packet,setPacket]=useState(null),[notes,setNotes]=useState(''),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function work(verdict){setBusy(true);setError('');try{if(verdict)await api.request(reviews+encodeURIComponent(packet.id),send({verdict,notes}));const r=await api.request(reviews+encodeURIComponent(id));setPacket(r);}catch(e){setError(e.message);}finally{setBusy(false);}}
 return <details className={styles.panel}><summary>Review a development workspace</summary><label>Assigned review ID <input disabled={busy} value={id} onChange={e=>{setId(e.target.value.trim());setPacket(null);setNotes('');}}/></label>
 <button disabled={!id||busy} onClick={()=>work()}>Open review</button>{error&&<p role="alert">{error}</p>}{packet&&<><p>Revision {packet.revision} · {packet.verdict||'Pending decision'}</p>
 {packet.candidate.files.map(f=><details key={f.path}><summary>{f.path}</summary><pre className={styles.output}>{f.content}</pre></details>)}<pre className={styles.output}>{JSON.stringify(packet.receipt,null,2)}</pre>
 <label>Review findings <textarea disabled={busy||!!packet.verdict} value={packet.notes||notes} onChange={e=>setNotes(e.target.value)}/></label>
 {['pass','fail'].map(v=><button key={v} disabled={busy||!!packet.verdict||notes.trim().length<15} onClick={()=>work(v)}>{v==='pass'?'Approve revision':'Reject revision'}</button>)}</>}</details>;
}
