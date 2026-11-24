// "Today": the Founder's first glance. Plain-language projection of the SAME
// signed delivery overview the Command Center reads. Read-only: it never
// infers approvals, runs or QA results that the server did not record.
import {founderDecisions,qaReworkStage,recoverableStage} from './founder-delivery-state.js';

export const STAGE_NAMES={discovery:'Discovery',architecture:'Architecture',implementation:'Build',quality:'Quality',release:'Release'};
const stageName=s=>STAGE_NAMES[s]||String(s||'Stage').replace(/^./,c=>c.toUpperCase());

// Plain words for the server's recorded follow-up codes (never exception text).
const FOLLOWUP_TEXT={
 recovery_limit_reached:'On hold after 6 automatic attempts. The AI CEO sent you a report. Start a rework when you are ready.',
 qa_rework:'QA sent the work back. The team is redoing it.',
 board_revision:'The Board asked for changes. The team is revising.',
 test_runner_unavailable:'Waiting for Docker to run the tests.',
 model_runner_unavailable:'Waiting for the local AI model (Ollama).',
 calendar_wait:'Waiting for the worker\'s working hours.',
 credit_budget_missing:'AI credits are not set. Set an allowance to continue.',
 credit_budget_exceeded:'AI credits ran out. Raise the allowance to continue.',
 failure_needs_founder:'The AI team could not fix this alone. Your review is needed.',
 project_not_active:'The project plan is not active yet.',
 no_ai_project_manager:'This project has no AI project manager.',
 stage_not_staffed:'No AI employee is assigned to this stage yet.',
 stage_specialist_unavailable:'The assigned AI employee is no longer available.',
};
/** One short sentence for a recorded follow-up. */
export function followupText(f){
 if(!f)return '';
 if(FOLLOWUP_TEXT[f.code])return FOLLOWUP_TEXT[f.code];
 const text=String(f.next_action||f.feedback||'').replace(/\s+/g,' ').trim();
 return text.length>140?text.slice(0,137)+'…':text;
}

/** Station state of one stage on the project line. */
export function stationState(stage,hold){
 if(stage.task_status==='completed'&&stage.qa_verdict==='pass')return 'passed';
 if(hold)return 'hold';
 if(stage.task_status==='failed'||stage.qa_verdict==='fail')return 'failed';
 if(stage.task_status==='running')return 'running';
 if(stage.task_status==='completed')return 'review';
 if(stage.task_status==='waiting_approval'||stage.task_status==='proposed')return 'waiting';
 return 'idle';
}
export const STATION_LABEL={passed:'Passed QA',hold:'On hold — needs you',failed:'Sent back',running:'AI team working',
 review:'Waiting for QA',waiting:'Waiting to start',idle:'Not started'};

const open=f=>f&&f.status!=='resolved';
/** Newest unresolved Founder-owned blocker per stage (the overview lists newest first). */
export function founderHolds(project,founderId){
 const seen=new Map();
 for(const f of Array.isArray(project?.followups)?project.followups:[]){
  if(!open(f)||f.status!=='blocked'||!founderId||f.owner_id!==founderId)continue;
  if(!seen.has(f.stage))seen.set(f.stage,f);
 }
 return seen;
}

/** The project as a line of stations plus one plain sentence for "now". */
export function projectLine(project,founderId){
 const holds=founderHolds(project,founderId);
 const stages=Array.isArray(project?.stages)?project.stages:[];
 const stations=stages.map(s=>{const state=stationState(s,holds.get(s.stage));return {
  stage:s.stage,name:stageName(s.stage),employee:s.employee||null,state,label:STATION_LABEL[state]};});
 const passed=stations.filter(s=>s.state==='passed').length;
 const current=stations.find(s=>s.state!=='passed')||null;
 let now;
 if(!stations.length)now='No stages yet.';
 else if(!current)now='All '+stations.length+' stages passed QA.';
 else{
  const latest=(Array.isArray(project.followups)?project.followups:[]).find(f=>open(f)&&f.stage===current.stage);
  now=current.name+': '+(latest?followupText(latest):current.label+'.');
 }
 return {project_id:project.project_id,title:project.title,manager:project.manager||null,stations,passed,total:stations.length,
  current:current?.stage||null,now,done:stations.length>0&&!current};
}

/** Everything that needs the Founder, in plain words: decisions first, then holds. */
export function needsYou(projects,founderId){
 const items=[];
 for(const p of Array.isArray(projects)?projects:[]){
  for(const d of founderDecisions(p))items.push({kind:'decision',key:'d:'+d.approval_id,project:p,approval_id:d.approval_id,
   title:d.label,detail:p.title});
  for(const [stageKey,f] of founderHolds(p,founderId)){
   const stage=(p.stages||[]).find(s=>s.stage===stageKey)||null;
   if(stage&&stage.task_status==='completed'&&stage.qa_verdict==='pass')continue;
   items.push({kind:'hold',key:'h:'+f.id,project:p,stage,followup:f,
    title:p.title+' · '+stageName(stageKey),detail:followupText(f),
    rework:Boolean(stage&&recoverableStage(stage)),qaRework:Boolean(stage&&qaReworkStage(stage))});
  }
 }
 return items;
}

/** One headline sentence from recorded counts only. */
export function headline({projects=[],needs=[],running=0}={}){
 const lines=projects.map(p=>projectLine(p));
 const active=lines.filter(l=>!l.done).length;
 const parts=[active===1?'1 project is active.':active+' projects are active.'];
 parts.push(needs.length?(needs.length===1?'1 thing needs you.':needs.length+' things need you.'):'Nothing needs you right now.');
 if(running)parts.push(running===1?'1 AI task is running.':running+' AI tasks are running.');
 return parts.join(' ');
}
