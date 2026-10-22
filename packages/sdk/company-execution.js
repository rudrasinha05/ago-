/** Pure UI gates: backend re-authorizes every action on dispatch. */
export const INTERNAL_AGENT_ACTIONS=Object.freeze(['internal:brief','research:brief']);
export function nextTaskAction(task,approval,permissions=[],busy=false){
 if(!task||busy)return {action:null,reason:busy?'In progress':'No verified task'};
 if(task.status==='proposed'){
  return permissions.includes('task:create')&&permissions.includes('approval:request')
   ?{action:'request',reason:'Submit exact task for independent approval'}
   :{action:null,reason:'Approval submission permission required'};
 }
 if(task.status==='waiting_approval'){
  if(!task.approval_id)return {action:null,reason:'Task approval ID missing'};
  if(!approval)return {action:null,reason:'Approval record unavailable'};
  if(approval.id!==task.approval_id||approval.action!==task.action)return {action:null,reason:'Approval does not match exact task action'};
  if(approval.status==='rejected')return {action:null,reason:'Task approval rejected'};
  if(approval.status!=='approved')return {action:null,reason:'Awaiting authorized reviewer'};
  if(!INTERNAL_AGENT_ACTIONS.includes(task.action))return {action:null,reason:'Specialized tool execution is handled separately in Operations & Tools'};
  if(!permissions.includes('agent:dispatch')||!permissions.includes('task:execute'))return {action:null,reason:'AI execution and task execution permissions required'};
  return {action:'run',reason:'Explicitly dispatch the reviewed, approved internal AI task'};
 }
 if(task.status==='running')return {action:null,reason:'Recorded running; do not dispatch twice'};
 if(task.status==='completed')return {action:null,reason:'Execution completed; independent QA needed'};
 if(task.status==='failed')return {action:null,reason:'Failed — inspect evidence and obtain a new authorized recovery'};
 return {action:null,reason:'Not eligible for governed dispatch'};
}
export function executionSummary(tasks){
 if(!Array.isArray(tasks))return null;
 return {proposed:tasks.filter(t=>t.status==='proposed').length,
         awaiting:tasks.filter(t=>t.status==='waiting_approval').length,
         running:tasks.filter(t=>t.status==='running').length,
         completed:tasks.filter(t=>t.status==='completed').length,
         failed:tasks.filter(t=>t.status==='failed').length};
}
