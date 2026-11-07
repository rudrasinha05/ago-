// One-line live summary of every company project (Founder portfolio).
// Built only from the signed delivery overview and the project list; it never
// infers QA, release, income or approval that the server did not record.
import {DELIVERY_STATES,founderDecisions,reviewedStages} from './founder-delivery-state.js';

export const PORTFOLIO_FILTERS=[
 ['all','All'],['needs_you','Needs your decision'],['running','Running'],
 ['blocked','Blocked'],['waiting','Waiting'],['done','Stages reviewed'],
];
const text=x=>typeof x==='string'&&x.trim()?x.trim():null;

/** Which filter a project belongs to; a Founder decision always comes first. */
export function portfolioGroup(project){
 if(founderDecisions(project).length)return 'needs_you';
 if(project.delivery_state==='blocked')return 'blocked';
 if(project.delivery_state==='internally_reviewed')return 'done';
 if(project.delivery_state==='working'||project.stages.some(s=>s.task_status==='running'||s.agent_run_status==='running'))return 'running';
 return 'waiting';
}

/** Manager first, then each distinct recorded stage employee. */
export function projectTeam(project){
 const names=[text(project.manager),...project.stages.map(s=>text(s.employee))].filter(Boolean);
 return [...new Set(names)];
}

function income(summary){
 const value=summary?.verified_revenue_inr;
 if(typeof value==='number'&&Number.isFinite(value)&&value>=0)return {verified:true,label:'₹'+value.toLocaleString('en-IN')+' (verified)'};
 return {verified:false,label:'No verified income yet'};
}

/** Rows for a delivery page, joined with the optional project list by id. */
export function portfolioRows(page,projects){
 const byId=new Map((Array.isArray(projects)?projects:[]).filter(p=>p&&typeof p.id==='string').map(p=>[p.id,p]));
 return page.projects.map(p=>{
  const summary=byId.get(p.project_id);
  const failed=p.stages.filter(s=>s.task_status==='failed'||s.agent_run_status==='failed'||s.qa_verdict==='fail').length;
  const running=p.stages.filter(s=>s.task_status==='running'||s.agent_run_status==='running').length;
  return {
   id:p.project_id,title:p.title,state:p.delivery_state,status:DELIVERY_STATES[p.delivery_state][0],
   group:portfolioGroup(p),reviewed:reviewedStages(p),stageCount:p.stages.length,running,failed,
   team:projectTeam(p),decisions:founderDecisions(p).length,
   commercial:text(summary?.commercial_stage)||'Not recorded',income:income(summary),
   released:p.release_ready===true,project:p,
  };
 });
}

export function portfolioCounts(rows){
 const counts=Object.fromEntries(PORTFOLIO_FILTERS.map(([key])=>[key,0]));
 for(const row of rows){counts.all++;counts[row.group]++;}
 return counts;
}
