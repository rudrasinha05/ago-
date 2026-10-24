/** Pure, fail-closed delivery status decisions from AGO authenticated records. */
export const sameRecord=(a,b)=>{
 const sorted=v=>Array.isArray(v)?v.map(sorted):v&&typeof v==='object'
  ?Object.fromEntries(Object.keys(v).sort().map(k=>[k,sorted(v[k])])):v;
 return Boolean(a&&b)&&JSON.stringify(sorted(a))===JSON.stringify(sorted(b));
};
export function githubDeliveryRows(project,operations,proposals){
 const status=project?.status;
 if(!status||status.repository_private!==true||!Array.isArray(status.operations))
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
  const applicable=Boolean(p&&approved&&!item.proposal_applied);
  return {id:operation.id,type:operation.operation,
   proposalId:p?.id||null,approved,applied:true,
   headOk,neverRetry,createdPr,committed,
   dispatch:event?.status||'not_started',
   commitSha:committed?recordedSha:null,
   prUrl:createdPr?event.result.url:null,
   label:operation.operation==='commit_files'?'AI-generated code commit':'Review-only draft Pull Request',
   eligibleExecute:approved&&headOk&&!neverRetry,
   blocker:!p?'Original independent governance proposal not visible.'
    :!approved?'Waiting for independent human governance approval.'
    :!headOk?'GitHub develop changed; inspect and re-review.'
    :neverRetry?(committed?'Verified commit delivered.':createdPr?'Verified draft PR delivered.':'Previous dispatch is recorded; inspect before retry.')
    :null};
 });
 return {health:'verified',rows,
  blocker:rows.length?'':'No approved GitHub delivery operations recorded yet.'};
}
