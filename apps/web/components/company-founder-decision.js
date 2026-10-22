/** Shared one-time Founder approval → bounded CEO handoff. */
const BASE='/v1/organization/company';
export async function decideFounderScope(api,request,approve,reason){
 if(!request||request.status!=='pending'||!request.requires_founder_decision)
  throw new Error('Only Founder scope decisions may use this action');
 if(!reason?.trim())throw new Error('Decision reason required');
 await api.request('/v1/governance/approvals/'+encodeURIComponent(request.id)+'/decision',{
  method:'POST',body:{approve,reason:reason.trim()}});
 if(!approve||!request.founder_intake_id||!request.plan_id)
  return {notice:approve?'Founder approved request.':'Founder denied request.'};
 try{
  const plan=encodeURIComponent(request.plan_id),project=encodeURIComponent(request.founder_intake_id);
  await api.request('/v1/brain/plans/'+plan+'/activate',{method:'POST'});
  await api.request('/v1/brain/plans/'+plan+'/materialize',{method:'POST'});
  const details=await api.request(BASE+'/projects/'+project);
  for(const stage of details.stages||[]){
   if(stage.task_id&&stage.task_status==='proposed'&&
      ['internal:brief','research:brief','project:plan'].includes(stage.task_action))
    await api.request('/v1/console/tasks/'+encodeURIComponent(stage.task_id)+'/request-approval',{method:'POST'});
  }
  const result=await api.request(BASE+'/projects/'+project+'/ceo/reconcile',{method:'POST'});
  return {notice:'Founder approved once. CEO '+result.ceo_name+
   ' verified '+result.verified_task_count+' in-scope tasks; execution is separate.'};
 }catch(error){
  return {notice:'Founder approval recorded; CEO handoff incomplete: '+(error.message||'Inspect board/plan')+
   '. Do not approve twice. Resume from Project Portfolio.',handoffNeedsAttention:true};
 }
}
