/** Canonical authorized read plan. Missing/denied resources remain unavailable. */
import {resource, uuid, validateProfile} from './session.js';
export const workspaces = Object.freeze(['overview','strategy','governance','organization','knowledge','tools','calendar','twin']);
export function readPlan(page, now = new Date()) {
  const start = new Date(now.getTime()-86400000).toISOString();
  const end = new Date(now.getTime()+30*86400000).toISOString();
  const plans = {
    overview: [['score','/v1/insights/scorecard'],['tasks','/v1/tasks'],['approvals','/v1/governance/approvals'],['brief','/v1/meta/brief']],
    strategy: [['goals','/v1/brain/goals'],['plans','/v1/brain/plans'],['approvals','/v1/governance/approvals']],
    governance: [['approvals','/v1/governance/approvals'],['tasks','/v1/tasks'],['motions','/v1/council/motions'],['reviews','/v1/console/task-reviews'],['qaqueue','/v1/console/qa-queue']],
    organization: [['departments','/v1/organization/departments']],
    knowledge: [['verified','/v1/knowledge/nodes'],['pending','/v1/knowledge/pending']],
    tools: [
      ['enrollments','/v1/tools/enrollments'],['rules','/v1/tools/automation/rules'],
      ['runs','/v1/tools/runs'],['tasks','/v1/tasks'],
      ['approvals','/v1/governance/approvals'],
      ['enterpriseModes','/v1/operations/enterprise/modes'],
      ['enterprisePlans','/v1/operations/enterprise/plans'],
      ['enterpriseCosts','/v1/operations/enterprise/costs'],
      ['enterpriseBudgets','/v1/operations/enterprise/budgets'],
      ['enterpriseAssets','/v1/operations/enterprise/marketplace'],
      ['enterpriseAssetUsage','/v1/operations/enterprise/marketplace/usage'],
      ['enterpriseTwin','/v1/operations/enterprise/twin'],
    ],
    calendar: [['events','/v1/operations/calendar?start='+encodeURIComponent(start)+'&end='+encodeURIComponent(end)]],
    twin: [['dna','/v1/meta/dna/active'],['snapshots','/v1/meta/snapshots'],['reflection','/v1/meta/reflection'],['dnarecords','/v1/meta/dna'],['recommendations','/v1/meta/recommendations'],['evaluations','/v1/meta/evaluations']],
  };
  if (!workspaces.includes(page)) throw new Error('Unknown workspace');
  return plans[page];
}
export async function loadWorkspace(api, page) {
  const data = await api.readMany(readPlan(page));
  if (page === 'organization') {
    const departments = resource(data,'departments');
    if (Array.isArray(departments)) {
      const result = await api.readMany(departments.map(d=>[d.id,'/v1/organization/employees?department_id='+uuid(d.id)]));
      const errors = Object.values(result).filter(x=>x.status!=='ok');
      data.employees = errors.length ? {...errors[0],data:null} : {status:'ok',data:Object.fromEntries(Object.entries(result).map(([id,x])=>[id,x.data]))};
    } else data.employees = {...data.departments,data:null};
  }
  return data;
}
export function twinDefaults(data) {
  return {profile:validateProfile(resource(data,'dna')?.profile || {qa_target_pct:85,backlog_limit:5,budget_alert_pct:80}),snapshotId:resource(data,'snapshots')?.[0]?.id || '',simulation:null};
}
/** Views change presentation only; API permissions remain the authority. */
export function dashboardRecords(data, me, departmentId) {
  const tasks = resource(data,'tasks');
  const approvals = resource(data,'approvals');
  const departments = resource(data,'departments');
  const employees = resource(data,'employees');
  const members = employees && departmentId ? employees[departmentId] : null;
  const memberIds = new Set(Array.isArray(members) ? members.map(x=>x.id) : []);
  return {
    tasks: Array.isArray(tasks) ? tasks : null,
    approvals: Array.isArray(approvals) ? approvals.filter(x=>x.status==='pending') : null,
    departments: Array.isArray(departments) ? departments : null,
    members: Array.isArray(members) ? members : null,
    departmentTasks: Array.isArray(tasks) && Array.isArray(members) ? tasks.filter(x=>memberIds.has(x.assignee_id)) : null,
    myTasks: Array.isArray(tasks) ? tasks.filter(x=>x.assignee_id===me.id) : null,
  };
}
