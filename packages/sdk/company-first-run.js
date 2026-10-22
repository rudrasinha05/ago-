/** Task bootstrap is an explicit founder action; roles alone create no work. */
export const FIRST_RUN_ACTIONS=Object.freeze([
 {value:'internal:brief',label:'Internal validation (no AI model required)',requiresModel:false},
 {value:'research:brief',label:'Real local AI research brief (Ollama required)',requiresModel:true}
]);
export function firstRunReadiness(employees,permissions,tasks){
 const eligible=(Array.isArray(employees)?employees:[]).filter(e=>e.kind==='ai');
 const canCreate=permissions?.includes('task:create')===true;
 const available=Array.isArray(tasks);
 return {
  eligible,
  canCreate,
  available,
  canStart:eligible.length>0&&canCreate&&available,
  reason:!available?'Authenticated task feed unavailable'
   :!eligible.length?'No actual AI employee exists; add an AI specialist to a department first'
   :!canCreate?'Your role cannot create governed tasks'
   :'Select a specialist, then propose a single governed task for separate approval'
 };
}
export function taskBootstrapBody(action,employeeId,employees){
 if(!FIRST_RUN_ACTIONS.some(x=>x.value===action))throw new Error('Unknown first-run task action');
 const worker=(Array.isArray(employees)?employees:[]).find(e=>e.id===employeeId);
 if(!worker||worker.kind!=='ai')throw new Error('A real AI employee must be selected');
 return {action,assignee_id:worker.id};
}
