"use client";

import {useCallback,useEffect,useState} from "react";

/** AGO-local document-level access. No browser storage, no GitHub sync. */
export function CompanyDocumentVault({api,project}) {
 const [docs,setDocs]=useState([]);
 const [people,setPeople]=useState([]);
 const [chosen,setChosen]=useState(null);
 const [title,setTitle]=useState("");
 const [body,setBody]=useState("");
 const [classification,setClassification]=useState("founder_only");
 const [revision,setRevision]=useState("");
 const [employee,setEmployee]=useState("");
 const [rationale,setRationale]=useState("");
 const [events,setEvents]=useState([]);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState("");
 const [note,setNote]=useState("");
 const path="/v1/organization/company";
 const documentPath=(id)=>path+"/documents/"+encodeURIComponent(id);
 const refresh=useCallback(async()=>{
   const id=encodeURIComponent(project.id);
   const [items,candidates]=await Promise.all([
     api.request(path+"/projects/"+id+"/documents"),
     api.request(path+"/projects/"+id+"/documents/eligible")
   ]);
   setDocs(items);setPeople(candidates);
 },[api,project.id]);
 useEffect(()=>{
   setChosen(null);setEvents([]);setNote("");setError("");
   refresh().catch(e=>setError(e.message||"Could not load secure documents"));
 },[refresh]);

 async function run(fn) {
   if(busy)return;setBusy(true);setError("");setNote("");
   try {await fn();}catch(e){setError(e.message||"AGO document permission request failed");}
   finally{setBusy(false);}
 }
 async function create(e){e.preventDefault();await run(async()=>{
   const item=await api.request(path+"/projects/"+encodeURIComponent(project.id)+"/documents",{
     method:"POST",body:{title:title.trim(),body,classification}
   });
   setTitle("");setBody("");await refresh();await open(item.id);
   setNote("Document saved to AGO local PostgreSQL. No GitHub upload.");
 });}
 async function open(id){
   const item=await api.request(documentPath(id));setChosen(item);
   setRevision(item.body);setEmployee("");setRationale("");
   setEvents(await api.request(documentPath(id)+"/audit"));
 }
 async function revise(e){e.preventDefault();if(!chosen)return;await run(async()=>{
   await api.request(documentPath(chosen.id)+"/revisions",{method:"POST",body:{body:revision}});
   await open(chosen.id);setNote("New immutable revision stored.");
 });}
 async function changeAccess(event) {if(!chosen||!employee)return;await run(async()=>{
   await api.request(documentPath(chosen.id)+"/permissions",{
     method:"POST",body:{grantee_id:employee,event,rationale:rationale.trim()}
   });
   await open(chosen.id);
   setNote(event==="grant"?"Specific employee now has document access.":"Access revoked. Next read will be denied.");
 });}

 return <section className="ago-document-vault" aria-label="AGO confidential project documents">
   <h4>Confidential documents · AGO local vault</h4>
   <p>Founder-only by default. A project member cannot read a document until you explicitly grant access to that exact document. No GitHub sync.</p>
   {error&&<p role="alert">{error}</p>}
   {note&&<p role="status">{note}</p>}
   <form onSubmit={create}>
    <h5>Create document</h5>
    <label>Title <input value={title} onChange={e=>setTitle(e.target.value)} required maxLength={180}/></label>
    <label>Classification
     <select value={classification} onChange={e=>setClassification(e.target.value)}>
      <option value="founder_only">Founder only — cannot share</option>
      <option value="project_restricted">Project restricted — explicit grant only</option>
     </select>
    </label>
    <label>Content <textarea value={body} onChange={e=>setBody(e.target.value)} rows={5} minLength={1} maxLength={20000} required/></label>
    <button disabled={busy||!title.trim()||!body.length}>Save locally</button>
   </form>
   <div aria-label="Saved AGO documents">
    <h5>Documents ({docs.length})</h5>
    {docs.length===0?<p>No documents saved for this project.</p>:
     <ul>{docs.map(d=><li key={d.id}>
       <button type="button" disabled={busy} onClick={()=>run(()=>open(d.id))}>
        {d.title} · {d.classification==="founder_only"?"Founder only":"Restricted"}
       </button>
     </li>)}</ul>}
   </div>
   {chosen&&<div>
     <h5>Selected document: {chosen.title}</h5>
     <p>Classification: {chosen.classification} · Revision {chosen.revision} · Local ID: <code>{chosen.id}</code></p>
     <form onSubmit={revise}>
       <label>Document content / next revision
        <textarea rows={6} value={revision} onChange={e=>setRevision(e.target.value)}
          required minLength={1} maxLength={20000}/>
       </label>
       <button disabled={busy||!revision.trim()||revision===chosen.body}>Save new revision</button>
     </form>
     {chosen.classification==="project_restricted"&&<div>
       <h5>Employee-by-employee document access</h5>
       <p>Only existing active human project members are eligible. AI workers cannot take your credentials.</p>
       <label>Employee
         <select value={employee} onChange={e=>setEmployee(e.target.value)}>
          <option value="">Select authorized project employee</option>
          {people.map(e=><option key={e.id} value={e.id}>{e.name} ({e.role_title||"Team member"})</option>)}
         </select>
       </label>
       <label>Reason for the permission change
         <input value={rationale} onChange={e=>setRationale(e.target.value)}
           minLength={8} maxLength={500} placeholder="Why this employee needs this exact document"/>
       </label>
       <div>
        <button type="button" disabled={busy||!employee||rationale.trim().length<8}
          onClick={()=>changeAccess("grant")}>Grant read access</button>
        <button type="button" disabled={busy||!employee||rationale.trim().length<8}
          onClick={()=>changeAccess("revoke")}>Revoke access</button>
       </div>
       {people.length===0&&<p>No eligible active human project member has been assigned. Grant is unavailable.</p>}
     </div>}
     <details>
      <summary>Document access audit ({events.length} most recent)</summary>
      <ol>{events.map((e,i)=><li key={i}>{e.action} · {String(e.actor_id)} · {new Date(e.occurred_at).toLocaleString()}</li>)}</ol>
     </details>
   </div>}
 </section>;
}
