/** Pure, fail-closed delivery status decisions from AGO authenticated records. */
export const sameRecord=(a,b)=>{
 const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
 return Boolean(a&&b)&&JSON.stringify(sorted(a))===JSON.stringify(sorted(b));
};
/** Exactly one successful real provider check/status for every reviewed name. */
export function verifiedGitHubChecks(status,names){
 if(!Array.isArray(names)||!names.length||names.length>24||
    names.some(x=>typeof x!=='string'||!x||x.length>120)||
    new Set(names).size!==names.length||
    status?.ci_truncated!==false||status?.ci_check_truncated!==false||
    status?.ci_status_truncated!==false||
    !Array.isArray(status?.ci_check_runs)||!Array.isArray(status?.ci_statuses)||
    !Number.isInteger(status?.ci_check_total)||
    status.ci_check_total!==status.ci_check_runs.length)return false;
 return names.every(name=>{
  const matches=[
   ...status.ci_check_runs.filter(x=>x?.name===name)
     .map(x=>x.status==='completed'&&x.conclusion==='success'),
   ...status.ci_statuses.filter(x=>x?.context===name)
     .map(x=>x.state==='success'),
  ];
  return matches.length===1&&matches[0]===true;
 });
}
export function githubDeliveryRows(project,operations,proposals){
 const status=project?.status;
 if(!status||status.repository_private!==true||!Array.isArray(status.operations)||
    status.project_id!==project.id||
    status.repository!=='rudrasinha05/'+project.repository)
  return {health:'unavailable',rows:[],blocker:status?.repository_private===false
   ?'This repository is public; private-source delivery is blocked.'
   :'Verified private GitHub project status is unavailable.'};
 const opRows=(operations||[]).filter(x=>{
  const operation=x?.payload;
  return x?.kind==='github_operation'&&operation?.project_id===project.id&&
   ['commit_files','create_pull_request'].includes(operation.operation);
 });
 const rows=opRows.map(item=>{
  const operation=item.payload;
  const p=(proposals||[]).find(x=>x.command==='github_operation'&&
   x.operation_key===operation.id&&x.specification?.id===operation.id&&
   sameRecord(x.specification,operation));
  const event=status.operations.find(x=>String(x.operation_id)===operation.id);
  const approved=p?.status==='approved';
  const executed=event?.status==='succeeded'&&event?.result&&typeof event.result==='object';
  const recordedSha=event?.result?.sha;
  const committed=operation.operation==='commit_files'&&executed&&
   typeof recordedSha==='string'&&/^[0-9a-f]{40}$/.test(recordedSha);
  const createdPr=operation.operation==='create_pull_request'&&executed&&
   Number.isSafeInteger(event.result.number)&&event.result.number>0&&
   event.result.url==='https://github.com/'+status.repository+'/pull/'+event.result.number&&
   event.result.head_sha===operation.payload?.expected_sha;
  const headOk=operation.payload?.expected_sha===status.develop_sha;
  const neverRetry=Boolean(event);
  const prChecksOk=operation.operation!=='create_pull_request'||
   verifiedGitHubChecks(status,operation.payload?.required_checks);
  return {id:operation.id,type:operation.operation,
   proposalId:p?.id||null,approved,
   headOk,neverRetry,createdPr,committed,
   dispatch:event?.status||'not_started',
   commitSha:committed?recordedSha:null,
   prUrl:createdPr?event.result.url:null,
   label:operation.operation==='commit_files'?'AI-generated code commit':'Review-only draft Pull Request',
   eligibleExecute:approved&&headOk&&prChecksOk&&!neverRetry,
   blocker:!p?'Original independent governance proposal not visible.'
    :!approved?'Waiting for independent human governance approval.'
    :!headOk?'GitHub develop changed; inspect and re-review.'
    :!prChecksOk?'Required GitHub CI checks incomplete or unverifiable.'
    :neverRetry?(committed?'Verified commit delivered.':createdPr?'Verified draft PR delivered.':'Previous dispatch is recorded; inspect before retry.')
    :null};
 });
 return {health:'verified',rows,
  blocker:rows.length?'':'No approved GitHub delivery operations recorded yet.'};
}
