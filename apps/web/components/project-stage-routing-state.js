// Founder stage assignment: UI only ranks employees from a fresh, scoped,
// read-only HR eligibility receipt. The backend ALWAYS rechecks on POST.
// A preview is never permission to hire, activate, execute or approve work.
const MATCH={
 discovery:/research|product|analyst|business/i,
 architecture:/architect|cto|engineering lead|tech/i,
 implementation:/engineer|developer|programmer|full.stack/i,
 quality:/qa|quality|test|reviewer/i,
 release:/release|devops|platform|sre|delivery/i,
};

export function verifiedStaffing(project,raw){
 if(project?.plan_status!=='active'||!raw||typeof raw!=='object'||Array.isArray(raw))return null;
 if(raw.kind!=='ago_p1_readonly_staffing_proposals'||raw.project_id!==project.id||
    raw.is_live_project_evidence!==true||raw.requires_founder_review!==true||
    raw.personnel_hired!==false||raw.permission_granted!==false||
    raw.charter_granted!==false||typeof raw.source_sha256!=='string'||
    !/^[0-9a-f]{64}$/.test(raw.source_sha256)||
    !Array.isArray(raw.eligible_employee_ids)||!Array.isArray(raw.proposals))return null;
 if(raw.eligible_employee_ids.some(id=>typeof id!=='string')||
    raw.proposals.some(p=>!p||typeof p.stage!=='string'||
      !Array.isArray(p.eligible_candidates)))return null;
 return raw;
}

export function stageCandidates(project,stage,employees=[],profiles=[],receipt=null){
 if(!stage||!project)return [];
 const staff=Array.isArray(employees)?employees:[];
 const roles=Array.isArray(profiles)?profiles:[];
 const workerName=id=>roles.find(p=>p.id===id)?.role_title||
   staff.find(e=>e.id===id)?.role_title||'Unconfigured role';
 const blocked=new Set([project.accountable_manager_id].filter(Boolean));
 const implementation=project.stages?.find(s=>s.stage==='implementation');
 const quality=project.stages?.find(s=>s.stage==='quality');
 if(stage.stage==='quality'){
  blocked.add(implementation?.approved_assignee_id);
  blocked.add(implementation?.suggested_assignee_id);
 }
 if(stage.stage==='implementation'){
  blocked.add(quality?.approved_assignee_id);
  blocked.add(quality?.suggested_assignee_id);
 }
 const safe=e=>e&&e.kind==='ai'&&typeof e.id==='string'&&
   !(stage.stage==='quality'||stage.stage==='implementation' ? blocked.has(e.id):false)&&
   (!stage.plan_step_id||!stage.suggested_assignee_id||e.id===stage.suggested_assignee_id);
 if(project.plan_status!=='active'){
  // Existing drafts still need manually reviewed proposals; backend validates
  // real HR state and exact project scope before any approval/activation.
  return staff.filter(safe);
 }
 const verified=verifiedStaffing(project,receipt);
 if(!verified)return [];
 if(stage.approved_assignee_id)return [];
 const active=new Set(verified.eligible_employee_ids);
 if(stage.suggested_assignee_id&&active.has(stage.suggested_assignee_id)){
  return staff.filter(e=>e.id===stage.suggested_assignee_id&&safe(e));
 }
 const proposal=verified.proposals.find(p=>p.stage===stage.stage);
 if(!proposal)return [];
 const permitted=new Set((proposal.eligible_candidates||[])
  .filter(c=>c&&typeof c.employee_id==='string')
  .map(c=>c.employee_id));
 return staff.filter(e=>permitted.has(e.id)&&active.has(e.id)&&safe(e))
  .sort((a,b)=>Number(!MATCH[stage.stage]?.test((a.name||'')+' '+workerName(a.id)))-
                Number(!MATCH[stage.stage]?.test((b.name||'')+' '+workerName(b.id))));
}

export function defaultStageCandidate(project,stage,employees,profiles,receipt){
 const candidates=stageCandidates(project,stage,employees,profiles,receipt);
 const configured=candidates.find(e=>e.id===stage?.suggested_assignee_id);
 if(configured)return configured.id;
 // Active projects use ONLY verified ordered shortlist. Drafts remain
 // advisory, and selecting a name still never approves an assignment.
 if(project?.plan_status==='active')return candidates[0]?.id||'';
 const title=id=>profiles?.find(p=>p.id===id)?.role_title||
   employees?.find(e=>e.id===id)?.role_title||'';
 return candidates.find(e=>MATCH[stage?.stage]?.test((e.name||'')+' '+title(e.id)))?.id||'';
}
