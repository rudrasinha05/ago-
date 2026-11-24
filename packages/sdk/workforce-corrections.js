/** ORG-016: the Employee Manager's correction proposal for the Founder.
 *
 * A proposal only. Nothing here writes: the Founder ticks rows and approves,
 * and each approved row uses the existing founder-only role / manager
 * endpoints, so identity, task history and permissions are untouched.
 *
 * Rules (Founder, 2026-11-24):
 * - an employee's designation, duties and expertise match who they are (their name);
 * - the hierarchy is Founder → CEO → department heads → managers → employees,
 *   with the CTO/CFO/CISO/CQO as the leadership a department head reports to
 *   when the area is theirs (otherwise the CEO);
 * - employees do not all report straight to the CEO.
 */

// Areas, checked in order; the first match wins (order matters: "Market
// Researcher" is marketing, "Strategic Planner" is strategy, "Test Engineer" is QA). `head` finds the department
// head among the employees of that area; `exec` names the Board seat it
// reports to (null = the CEO).
export const AREAS=[
 {key:'qa',name:'Quality Assurance',match:/\b(qa|test|tester|quality)\b/i,head:/\b(qa|quality)\b.*\bmanager\b/i,exec:'Quality & Release',
  duty:['Independent testing of approved work','Test plans, automated and manual tests, defects and acceptance evidence','Executed test results and QA verdicts']},
 {key:'security',name:'Security & Compliance',match:/\b(security|compliance|risk|privacy)\b/i,head:/\bsecurity\b.*\bmanager\b/i,exec:'Risk & Compliance',
  duty:['Security and compliance of company work','Threat review, access control, privacy and policy evidence','Security findings and compliance records']},
 {key:'finance',name:'Finance',match:/\b(finance|financial|cost|budget|account\w*)\b/i,head:/\bfinance\b.*\b(manager|lead|controller)\b/i,exec:'Finance & Budget',
  duty:['Costs, budgets and unit economics','Cost evidence, forecasts and spending proposals (no payments)','Traceable cost and budget reports']},
 {key:'data',name:'Data & Analytics',match:/\bdata\b/i,head:/\bdata\b.*\b(manager|lead)\b/i,exec:'Technology Oversight',
  duty:['Data pipelines and analysis','Datasets, SQL, data quality and metrics','Validated datasets and source-linked analysis']},
 {key:'platform',name:'Platform & Release',match:/\b(devops|build|infrastructure|release|platform|sre)\b/i,head:/\b(devops|platform)\b.*\b(manager|lead)\b/i,exec:'Technology Oversight',
  duty:['Build, infrastructure and release','CI, Docker, environments and release packaging','Reproducible builds and release packages']},
 {key:'design',name:'Design & UX',match:/\b(design\w*|ui|ux)\b/i,head:/\bdesign\b.*\b(manager|lead)\b/i,exec:'Technology Oversight',
  duty:['User experience and interface design','User research, flows, accessibility and visual design','Reviewed UX and UI specifications']},
 {key:'marketing',name:'Marketing & Customers',match:/\b(market\w*|sales|growth|customer|content)\b/i,head:/\bmarketing\b.*\bmanager\b/i,exec:null,
  duty:['Marketing and customer work','Market research, content, customer success and growth','Reviewed market and customer evidence']},
 {key:'research',name:'Research',match:/\b(research\w*|experiment\w*|scientist)\b/i,head:/\bresearch\b.*\b(manager|director|lead)\b/i,exec:'Technology Oversight',
  duty:['Research and experiments','Hypotheses, methods, experiments and reproducible findings','Reviewed research reports']},
 {key:'engineering',name:'Software Engineering',match:/\b(engineer\w*|developer|architect|programmer|software)\b/i,head:/\bengineering\b.*\bmanager\b/i,exec:'Technology Oversight',
  duty:['Software implementation','Source code, unit tests, APIs, integration and technical documentation','Working code with passing tests']},
 {key:'project',name:'Project Delivery',match:/\b(project|delivery|program)\b/i,head:/\bproject manager\b/i,exec:null,
  duty:['Project delivery','Scope, milestones, staffing, blockers and handoffs','Project plan and delivery ledger']},
 {key:'people',name:'People & Learning',match:/\b(people|hr|talent|skills?|learning)\b/i,head:/\bpeople\b.*\bmanager\b/i,exec:null,
  duty:['People and learning','Roles, skills, onboarding and learning plans','Skills matrix and staffing proposals']},
 {key:'strategy',name:'Strategy & Business Analysis',match:/\b(strateg\w*|business|requirements?)\b/i,head:/\bstrategy\b.*\bmanager\b/i,exec:null,
  duty:['Strategy and business analysis','Requirements, business cases, priorities and acceptance criteria','Reviewed requirements and strategy documents']},
 {key:'operations',name:'Operations',match:/\b(operations?|resource|planner|coordinator)\b/i,head:/\boperations\b.*\bmanager\b/i,exec:null,
  duty:['Company operations','Capacity, scheduling, resources and process follow-through','Operations plans and resource reports']},
 {key:'knowledge',name:'Knowledge & Documentation',match:/\b(knowledge|writer|documentation|curator)\b/i,head:/\bknowledge\b.*\bmanager\b/i,exec:null,
  duty:['Company knowledge and documentation','Documentation, knowledge base and curation','Sourced documents and knowledge records']},
];

const SEAT_CEO='Strategy & Vision';
const PROTECTED=/^(ai )?project manager( \(pm\))?$|^technical project manager$/i;

/** The area an employee belongs to, by name first, then by recorded title. */
export function areaFor(name,title=''){
 return AREAS.find(a=>a.match.test(String(name||'')))||AREAS.find(a=>a.match.test(String(title||'')))||null;
}

/** Duties that match the employee's own name. */
export function dutyFor(name,title=''){
 const area=areaFor(name,title);
 if(!area)return null;
 const [workArea,focus,deliverable]=area.duty;
 return {area:area.name,core:'Work area: '+workArea+'. Core duties: '+focus+'. Expected deliverable: '+deliverable+'. Report progress and blockers to your recorded manager.',focus};
}

const isHead=(area,e)=>area&&area.head.test(String(e.name||''));

/**
 * The correction proposal. Returns one row per employee that needs a change:
 * {id,name,area,changes:['designation'|'reporting'],current_title,proposed_title,
 *  proposed_core,current_manager_id,proposed_manager_id,proposed_manager_name,reason,level}
 * plus `notes` for things the Founder should know (e.g. an area with no head).
 */
export function buildWorkforceCorrections({employees=[],profiles=[],board=[],founderId}){
 const people=employees.filter(e=>e&&e.id&&e.id!==founderId&&e.kind!=='human');
 const byId=new Map(employees.map(e=>[e.id,e]));
 const profile=new Map(profiles.map(p=>[p.id,p]));
 const seat=new Map(board.filter(b=>b?.employee_id).map(b=>[b.seat,String(b.employee_id)]));
 const boardIds=new Set(seat.values());
 const ceo=seat.get(SEAT_CEO)||null;
 const notes=[];
 if(!ceo)return {rows:[],notes:['No AI CEO is appointed on the Board, so no reporting line can be proposed. Appoint the CEO first.']};
 // Department heads per area: the first matching employee (stable by name).
 const sorted=[...people].sort((a,b)=>String(a.name).localeCompare(String(b.name))||String(a.id).localeCompare(String(b.id)));
 const heads=new Map();
 for(const e of sorted){
  if(boardIds.has(e.id))continue;
  const area=areaFor(e.name);
  if(area&&isHead(area,e)&&!heads.has(area.key))heads.set(area.key,e.id);
 }
 const leaderOf=area=>(area?.exec&&seat.get(area.exec))||ceo;
 const rows=[];
 for(const e of sorted){
  const current=profile.get(e.id)||{};
  const currentTitle=String(current.role_title||e.role_title||'').trim();
  let proposedManager,level,why;
  const area=areaFor(e.name,currentTitle);
  if(e.id===ceo){proposedManager=founderId;level=1;why='The CEO reports to the Founder.';}
  else if(boardIds.has(e.id)){proposedManager=ceo;level=2;why='Board leadership reports to the CEO.';}
  else if(area&&heads.get(area.key)===e.id){
   proposedManager=leaderOf(area);level=3;
   why=area.key==='project'?'A Project Manager reports to the CEO (AGO requires it to lead a project).'
    :'Head of '+area.name+'; reports to '+(proposedManager===ceo?'the CEO':(byId.get(proposedManager)?.name||'its Board leader'))+'.';
  }else if(area&&heads.get(area.key)){proposedManager=heads.get(area.key);level=4;why='Works in '+area.name+' under its head.';}
  else{
   proposedManager=leaderOf(area);level=4;
   why=area?'No head for '+area.name+' yet, so reports to '+(proposedManager===ceo?'the CEO':(byId.get(proposedManager)?.name||'its Board leader'))+'.'
    :'No matching area, so reports to the CEO until the Founder decides.';
  }
  const changes=[];
  // Board members keep their executive titles; the PM keeps the title AGO checks.
  let proposedTitle=currentTitle,proposedCore=current.core_responsibilities||'';
  if(!boardIds.has(e.id)&&!PROTECTED.test(currentTitle)){
   const name=String(e.name||'').trim();
   if(name&&currentTitle.toLowerCase()!==name.toLowerCase()){
    proposedTitle=name;
    const d=dutyFor(name,currentTitle);
    if(d)proposedCore=d.core;
    changes.push('designation');
   }
  }
  if(proposedManager&&proposedManager!==e.manager_id&&proposedManager!==e.id)changes.push('reporting');
  if(!changes.length)continue;
  rows.push({id:e.id,name:e.name,area:area?.name||'Unclassified',level,changes,
   current_title:currentTitle||'Not set',proposed_title:proposedTitle,proposed_core:proposedCore,
   current_manager_id:e.manager_id||null,current_manager_name:e.manager_id===founderId?'Founder':(byId.get(e.manager_id)?.name||'None'),
   proposed_manager_id:proposedManager,proposed_manager_name:proposedManager===founderId?'Founder':(byId.get(proposedManager)?.name||'Unknown'),
   reason:why});
 }
 for(const a of AREAS){
  const members=people.filter(e=>!boardIds.has(e.id)&&areaFor(e.name)?.key===a.key);
  if(members.length>1&&!heads.get(a.key))notes.push(a.name+' has '+members.length+' employees but no head; they report to '+(a.exec?'its Board leader':'the CEO')+'.');
 }
 // Apply order: top of the tree first, so no circular link is ever needed.
 rows.sort((a,b)=>a.level-b.level||String(a.name).localeCompare(String(b.name)));
 return {rows,notes};
}
