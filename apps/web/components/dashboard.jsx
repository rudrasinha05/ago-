"use client";
import {useEffect,useState} from 'react';
import {loadWorkspace,dashboardRecords} from '@ago/sdk/workspace';
import {resource} from '@ago/sdk/session';
import {Button,Metric,Panel,Records,Loading,Field,Notice} from '@ago/ui/components';
export function Dashboard({api,me,data}) {
  const [view,setView]=useState(me.permissions.includes('brain:manage')?'executive':'employee');
  const [organization,setOrganization]=useState(null), [department,setDepartment]=useState('');
  useEffect(()=>{
    let active=true;setOrganization(null);setDepartment('');
    if(view==='department')loadWorkspace(api,'organization').then(x=>{if(active){setOrganization(x);setDepartment(resource(x,'departments')?.[0]?.id || '');}}).catch(()=>{if(active)setOrganization({});});
    return ()=>{active=false;};
  },[api,me,view]);
  const records=dashboardRecords({...data,...organization},me,department);
  const score=resource(data,'score');
  return <section aria-label="Role dashboards" className="role-dashboard">
    <div className="dashboard-tabs" role="group" aria-label="Choose dashboard">{['executive','department','employee'].map(x=><Button key={x} aria-pressed={view===x} onClick={()=>setView(x)}>{x[0].toUpperCase()+x.slice(1)} dashboard</Button>)}</div>
    {view==='executive'&&<Panel title="Executive dashboard"><div className="metric-grid"><Metric label="Governed tasks" value={score?.counts?.tasks} note="Authorized organization records"/><Metric label="Pending decisions" value={records.approvals?.length} note="Independent human review"/></div><Records rows={records.approvals} label="Approval queue" empty="No pending decisions"/></Panel>}
    {view==='employee'&&<Panel title="Employee dashboard"><Metric label="My assigned tasks" value={records.myTasks?.length} note="Assignments matching your signed-in identity"/><Records rows={records.myTasks} label="Personal tasks" empty="No tasks assigned to you"/></Panel>}
    {view==='department'&&<Panel title="Department dashboard">{organization===null?<Loading />:records.departments===null?<Notice>Departments unavailable to your role or temporarily unavailable.</Notice>:<><Field id="dashboard-department" label="Department"><select id="dashboard-department" value={department} onChange={e=>setDepartment(e.target.value)}>{records.departments.map(x=><option key={x.id} value={x.id}>{x.name}</option>)}</select></Field><div className="metric-grid"><Metric label="Team members" value={records.members?.length} note="Human and AI employee records"/><Metric label="Team tasks" value={records.departmentTasks?.length} note="Tasks assigned to department members"/></div><Records rows={records.departmentTasks} label="Department tasks" empty="No tasks assigned to this team"/></>}</Panel>}
  </section>;
}
