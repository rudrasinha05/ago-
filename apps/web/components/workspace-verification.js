import {githubDeliveryRows,sameRecord,verifiedGitHubChecks} from './company-github-delivery-state.js';

export function verifyWorkspaceDelivery({project,task,goal,workspace,attempts,review,registered,status,catalog,proposals}){
 const sha=workspace.candidate_sha256;
 const repair=workspace.repair;
 if(!repair||repair.provider!=='ollama_local'||!repair.model||repair.parent_revision+1!==workspace.revision)
  throw new Error('No recorded local-model repair for this revision.');
 const failed=attempts.find(a=>a.attempt_id===repair.failed_attempt_id&&a.revision===repair.parent_revision);
 if(!failed||failed.candidate_sha256!==repair.parent_sha256||failed.receipt?.candidate_sha256!==repair.parent_sha256||
    failed.receipt.status!=='failed'||failed.receipt.tests_executed!==true)
  throw new Error('Missing matching failed Docker run before the repair.');
 if(review.project_id!==project||review.task_id!==task||review.run_id!==workspace.run_id||
    review.revision!==workspace.revision||review.candidate_sha256!==sha||review.verdict!=='pass'||
    !review.reviewer_id||!sameRecord(review.candidate?.files,workspace.files))
  throw new Error('Independent QA has not approved these exact files and revision.');
 const passed=attempts.find(a=>a.revision===workspace.revision&&a.candidate_sha256===sha&&sameRecord(a.receipt,review.receipt));
 if(!passed||passed.receipt.status!=='passed'||passed.receipt.docker_exit_code!==0||
    passed.receipt.tests_executed!==true||passed.receipt.tests_passed!==true||passed.receipt.candidate_sha256!==sha||
    !Number.isInteger(passed.receipt.unittest_cases)||passed.receipt.unittest_cases<1)
  throw new Error('Missing successful Docker retest matching the QA evidence.');
 if(!registered||registered.goal_id!==goal||registered.enabled!==true)
  throw new Error('No enabled GitHub repository matches the project goal.');
 const {rows,health}=githubDeliveryRows({...registered,status},catalog.github_operations,proposals);
 if(health!=='verified')throw new Error('Private GitHub repository binding could not be verified.');
 const operations=new Map(catalog.github_operations.map(r=>[r.payload?.id,r.payload]));
 const commit=rows.find(r=>r.approved&&r.committed&&r.commitSha===status.develop_sha&&
   sameRecord(operations.get(r.id)?.payload?.files,workspace.files)&&proposals.some(p=>
    p.id===r.proposalId&&p.rationale==='Workspace revision '+workspace.revision+' passed independent QA '+review.id));
 if(!commit)throw new Error('No approved commit at the current develop SHA matches this QA handoff.');
 const pr=rows.find(r=>r.approved&&r.createdPr&&operations.get(r.id)?.payload?.expected_sha===commit.commitSha&&
   verifiedGitHubChecks(status,operations.get(r.id)?.payload?.required_checks));
 if(!pr)throw new Error('Missing successful required CI or the matching AGO draft PR receipt.');
 return {model:repair.model,revision:workspace.revision,sha:commit.commitSha,url:pr.prUrl};
}
