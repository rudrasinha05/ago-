/** Founder-reviewable organization staffing blueprint. Profiles describe work areas, not proven abilities. */
const duty=(title,area,focus,deliverable)=>({title,area,focus,deliverable});
const CATALOG=[
 {pattern:/executive|leadership|board|management|corporate|strategy|office of ceo/,name:'Executive Office',roles:[
  duty('Chief of Staff','Cross-company coordination','Portfolio governance, ownership mapping','Dependency register and escalation decisions'),
  duty('Strategic Planning Lead','Company strategy','Market hypotheses, objectives and prioritization','Reviewed business roadmap'),
  duty('Portfolio Operations Manager','Program oversight','Capacity, risk and project milestones','Portfolio dashboard and delivery follow-through'),
  duty('Executive Reporting Analyst','Company reporting','Evidence verification, executive synthesis','Source-linked performance briefs')]},
 {pattern:/product|business analysis|business design/,name:'Product Management',roles:[
  duty('Head of Product','Product strategy','User needs, value proposition, prioritization','Approved product requirements'),
  duty('Product Research Analyst','Problem discovery','Interviews, assumptions, competitor research','Evidence-backed research brief'),
  duty('Product Owner','Scope and backlog','Acceptance criteria, user stories, roadmap','Groomed scoped backlog'),
  duty('Product Analytics Specialist','Product outcomes','Adoption, funnels, experiments','Reviewed outcomes and KPI report')]},
 {pattern:/research|innovation|r&d|ai research/,name:'Research & Innovation',roles:[
  duty('Research Director','Research governance','Hypothesis design, methodology, reproducibility','Reviewed experimental roadmap'),
  duty('Applied AI Researcher','Model and algorithm studies','ML, benchmarking, prompt evaluation','Reproducible research artifacts'),
  duty('Research Engineer','Research implementation','Dataset validation, experiments, performance','Versioned experiment code'),
  duty('Technical Writer & IP Analyst','Research publication','Literature review, claims and citations','Sourced reports and publication drafts')]},
 {pattern:/design|ux|ui|creative/,name:'Design & UX',roles:[
  duty('Product Design Lead','Interaction architecture','Design systems, usability and accessibility','Approved UX specifications'),
  duty('UX Researcher','Human-centered research','User interviews, tasks, accessibility feedback','Sourced usability findings'),
  duty('UI Designer','Visual interfaces','Components, typography, responsive flows','Editable visual specifications'),
  duty('Design Systems Engineer','Design implementation','Component tokens, semantic UI, accessibility','Verified reusable interface components')]},
 {pattern:/frontend|web|mobile|android|ios|app/,name:'Application Engineering',roles:[
  duty('Frontend Engineering Lead','UI technical ownership','React, Next.js, architecture and accessibility','Reviewed frontend architecture'),
  duty('Web Application Engineer','Web implementation','Frontend state, routing, tests','Working responsive pages and unit tests'),
  duty('Mobile Application Engineer','Mobile applications','Android/mobile lifecycle, UX and API integration','Tested mobile modules'),
  duty('Accessibility & UI QA Engineer','Client quality','Keyboard, screen-reader and cross-device behavior','Browser and accessibility evidence')]},
 {pattern:/engineer|development|software|technology|backend|\bit\b/,name:'Software Engineering',roles:[
  duty('Engineering Manager','Technical delivery ownership','Architecture reviews, risk and team unblock','Technical plans and accountable handoffs'),
  duty('Backend API Engineer','Service implementation','FastAPI, endpoints, authorization and contracts','Tested typed APIs'),
  duty('Full-Stack Engineer','Feature implementation','Frontend/backend integration and debugging','End-to-end working modules'),
  duty('Integration Engineer','System connectivity','External APIs, idempotency and error recovery','Verified connectors and integration tests'),
  duty('Developer Productivity Engineer','Source and tooling','Build scripts, lint, local workflows and CI','Reproducible code and tools')]},
 {pattern:/data|analytics|intelligence|machine learning|ml/,name:'Data & Intelligence',roles:[
  duty('Data Science Lead','Model strategy','Dataset lineage, evaluation and responsible AI','Approved evaluation plan'),
  duty('Data Engineer','Data pipelines','PostgreSQL, ETL, quality and lineage','Reliable validated datasets'),
  duty('ML Engineer','Model implementation','Inference, offline benchmarking and monitoring','Versioned model workflows'),
  duty('Business Intelligence Analyst','Metrics and dashboards','SQL, KPI definitions and reporting','Source-linked business dashboards')]},
 {pattern:/devops|cloud|platform|infrastructure|sre/,name:'Platform & Reliability',roles:[
  duty('Platform Engineering Lead','Infrastructure architecture','Runtime, release controls and capacity','Reviewed deployment architecture'),
  duty('DevOps & CI Engineer','Build and delivery','CI workflows, Docker, artifacts','Reproducible green builds'),
  duty('Site Reliability Engineer','Operational continuity','Health, incident recovery, resource limits','Measured reliability and recovery reports'),
  duty('Database Reliability Engineer','Persistent data','Migrations, backup, restore and performance','Verified database recovery evidence')]},
 {pattern:/security|cyber|compliance|legal|risk/,name:'Security & Governance',roles:[
  duty('Security Architect','Threat and access design','RBAC, secrets, encryption, threat models','Verified security design and controls'),
  duty('Application Security Engineer','Secure implementation','Input validation, auth and security testing','Security findings and remediation'),
  duty('Compliance & Risk Analyst','Policy and audit','Evidence, privacy, retention, legal review','Auditable policy and risk register'),
  duty('Incident Response Analyst','Security operations','Alerts, containment and incident evidence','Reviewed incident response packet')]},
 {pattern:/quality|qa|test|verification/,name:'Quality Assurance',roles:[
  duty('QA Manager','Independent release quality','Test planning, evidence and acceptance','Independent QA plan and verdicts'),
  duty('Automation Test Engineer','Automated validation','Integration, browser and regression tests','Repeatable test suites and results'),
  duty('Performance & Reliability Tester','Nonfunctional testing','Load, latency, stability and failure recovery','Measured performance evidence'),
  duty('Release Acceptance Analyst','Release verification','Traceability, requirements and defects','Signed-off quality evidence for founder review')]},
 {pattern:/project|delivery|pmo|operations|workflow/,name:'Project Delivery',roles:[
  duty('Program Manager','Cross-team delivery','Dependencies, milestone accountability and escalation','Reviewed milestone and delivery ledger'),
  duty('Technical Project Manager','Engineering coordination','Scoped tickets, blockers and resource planning','Assigned technical work packages'),
  duty('Scrum & Workflow Coordinator','Delivery cadence','Handoffs, cycle times and standups','Updated workflow and blocker reports'),
  duty('Delivery Documentation Specialist','Project records','Release notes, manuals, traceability','Versioned project evidence')]},
 {pattern:/marketing|growth|sales|commercial|customer success/,name:'Growth & Commercial',roles:[
  duty('Growth Strategy Lead','Market entry','Value proposition, channels and customer validation','Reviewed go-to-market hypothesis'),
  duty('Market Research Analyst','Market evidence','Buyer interviews, source provenance, pricing','Customer/competitor research dossier'),
  duty('Sales Enablement Specialist','Commercial operations','Qualified outreach proposals, demos and followups','Consent-aware sales documentation'),
  duty('Customer Success Specialist','Customer outcomes','Onboarding, support and feedback','Resolved verified customer cases')]},
 {pattern:/finance|account|economic|budget/,name:'Finance & Economics',roles:[
  duty('Finance Controller','Financial integrity','Budget policies, invoice reconciliation and audit','Reviewed cost and revenue records'),
  duty('Financial Analyst','Unit economics','Runway, unit costs, ROI and forecast assumptions','Traceable financial forecasts'),
  duty('Cost Optimization Analyst','Provider and resource costs','Compute/storage/tool billing reconciliation','Verified cost reduction proposals'),
  duty('Procurement Specialist','Vendor lifecycle','Vendor assessment, approvals and purchase controls','Reviewed sourcing recommendations')]},
 {pattern:/human|people|talent|hr|employee/,name:'People Operations',roles:[
  duty('People Operations Lead','Workforce policy','Hiring plans, roles, organizational structure','Approved staffing plans'),
  duty('Talent & Skills Coordinator','Competency development','Skill evidence, onboarding, learning','Maintained skills and development matrix'),
  duty('Workforce Capacity Analyst','Workload coordination','Availability, assignment fit, burnout indicators','Evidence-backed staffing suggestions'),
  duty('Employee Experience Specialist','Internal support','Grievances, feedback and well-being guardrails','Escalated support and policy proposals')]},
 {pattern:/support|service|helpdesk|success/,name:'Customer & Internal Support',roles:[
  duty('Support Operations Lead','Support organization','Triage, escalation and response planning','Service coverage plan'),
  duty('Technical Support Specialist','Incident troubleshooting','Reproduction, debugging and knowledge base','Resolved and documented support cases'),
  duty('Support Knowledge Specialist','Documentation','FAQs, self-service and accessibility','Sourced support guides'),
  duty('Customer Quality Specialist','Customer feedback','Defect intake, prioritization and resolution','Validated customer issue reports')]}
];
const FALLBACK=[
 duty('Operations Coordinator','Unclassified department','Inventory, work intake and escalation','Department responsibility register'),
 duty('Business Operations Analyst','Unclassified department','Process maps, performance and evidence','Process improvement proposals'),
 duty('Documentation & Quality Specialist','Unclassified department','Documentation, QA evidence and traceability','Audited departmental deliverables'),
 duty('Project Support Specialist','Unclassified department','Tickets, support and internal handoffs','Work queue and blocker reports')];
export function departmentBlueprint(name){
 const key=String(name||'').trim().toLowerCase();
 const priority=['Security & Governance','Quality Assurance','People Operations','Finance & Economics','Growth & Commercial','Platform & Reliability','Data & Intelligence','Research & Innovation','Design & UX','Application Engineering','Software Engineering','Product Management','Executive Office','Project Delivery'];
 return CATALOG.filter(entry=>entry.pattern.test(key)).sort((a,b)=>priority.indexOf(a.name)-priority.indexOf(b.name))[0]||{name:'Unclassified Department',roles:FALLBACK};
}
export function hasVerifiedProfile(employee,profile){
 const title=String(profile?.role_title||'').trim();
 const core=String(profile?.core_responsibilities||'').trim();
 // An existing meaningful, founder-entered responsibility is never overwritten.
 return Boolean(title&&title.toLowerCase()!=='not assigned'&&core&&core.toLowerCase()!=='not configured');
}
export function buildCompanyRolePlan(employees,departments,profiles,founderId){
 const byDepartment=new Map(departments.map(d=>[d.id,d]));
 const byProfile=new Map(profiles.map(p=>[p.id,p]));
 const groups=new Map();
 for(const employee of employees){
  if(employee.id===founderId)continue;
  const key=employee.department_id||'unassigned';
  if(!groups.has(key))groups.set(key,[]);
  groups.get(key).push(employee);
 }
 const result=[];
 for(const [deptId,members] of groups){
  const department=byDepartment.get(deptId),profile=departmentBlueprint(department?.name);
  const people=[...members].sort((a,b)=>a.name.localeCompare(b.name)||String(a.id).localeCompare(String(b.id)));
  people.forEach((employee,i)=>{
   const current=byProfile.get(employee.id);
   const specialization=profile.roles[i%profile.roles.length];
   const keep=hasVerifiedProfile(employee,current);
   const currentTitle=String(current?.role_title||'').trim();
   const meaningfulTitle=currentTitle&&currentTitle!==employee.name&&currentTitle.toLowerCase()!=='not assigned';
   const role_title=meaningfulTitle?currentTitle:specialization.title;
   const core_responsibilities='Work area: '+specialization.area+'. Core duties: '+specialization.focus+'. Expected deliverable: '+specialization.deliverable+'. Report progress and blockers to recorded manager.';
   const extra_responsibilities='Proposed expertise focus (not a verified skill assessment): '+specialization.focus+'. Cross-team collaboration, quality evidence, documentation, security/privacy and reproducible handoffs. Project execution requires a separately approved task, actual tools and CEO-led quality verification.';
   result.push({id:employee.id,name:employee.name,kind:employee.kind,department:department?.name||'Department not recorded',manager_id:employee.manager_id||null,role_title:keep?current.role_title:role_title,core_responsibilities:keep?current.core_responsibilities:(String(current?.core_responsibilities||'').trim()||core_responsibilities),extra_responsibilities:keep?current.extra_responsibilities:(String(current?.extra_responsibilities||'').trim()||extra_responsibilities),status:keep?'configured':'proposed',focus:specialization.focus});
  });
 }
 return result.sort((a,b)=>a.department.localeCompare(b.department)||a.name.localeCompare(b.name));
}

const EXECUTIVES=[
 {seat:'Strategy & Vision',title:'Chief Executive Officer (CEO)',match:/\bceo\b|chief executive|executive|strategy|portfolio|business/i,
  work:'Own every Founder-approved project: business roadmap, staffing, verified task delegation, project delivery and escalation. Never override the Founder scope.'},
 {seat:'Technology Oversight',title:'Chief Technology Officer (CTO)',match:/\bcto\b|chief technology|engineering|architect|software|technical/i,
  work:'Own architecture, secure code implementation, technical staffing, integrations, GitHub CI and error remediation; report to CEO.'},
 {seat:'Finance & Budget',title:'Chief Financial Officer (CFO)',match:/\bcfo\b|finance|budget|account|cost/i,
  work:'Maintain real cost evidence, ROI, virtual budgets and spending proposals; no payment authorization; report to CEO.'},
 {seat:'Risk & Compliance',title:'Chief Information Security Officer (CISO)',match:/\bciso\b|security|cyber|risk|compliance/i,
  work:'Verify security risks, privacy, compliance, access and incident evidence; report to CEO.'},
 {seat:'Quality & Release',title:'Chief Quality Officer (CQO)',match:/\bcqo\b|quality|\bqa\b|tester|test|release/i,
  work:'Own automated tests, acceptance criteria, regression reports and release blockers; report to CEO.'}
];
export function buildLeadershipPlan(employees,profiles,board,founderId,departments=[]){
 const ai=(employees||[]).filter(e=>e.kind==='ai'&&e.id!==founderId);
 const current=new Map((profiles||[]).map(p=>[p.id,p]));
 const departmentsById=new Map((departments||[]).map(d=>[d.id,d.name]));
 const assigned=new Map((board||[]).map(b=>[b.seat,String(b.employee_id)]));
 const used=new Set();
 return EXECUTIVES.map(x=>{
  const existing=ai.find(e=>e.id===assigned.get(x.seat)&&!used.has(e.id));
  const options=ai.filter(e=>!used.has(e.id)).map(e=>{
   const personal=[e.name,e.role_title,current.get(e.id)?.role_title].filter(Boolean).join(' ');
   const departmentName=departmentsById.get(e.department_id)||'';
   return {e,score:x.match.test(personal)?20:x.match.test(departmentName)?7:0};
  }).sort((a,b)=>b.score-a.score||String(a.e.id).localeCompare(String(b.e.id)));
  // Do not promote an unrelated engineer merely to fill a title; keep vacancy visible.
  const candidate=existing||(options[0]?.score>0?options[0].e:null);
  if(candidate)used.add(candidate.id);
  return {seat:x.seat,title:x.title,work:x.work,employee_id:candidate?.id||null,
   employee_name:candidate?.name||'Vacant — founder must hire an AI employee',existing:!!existing};
 });
}
