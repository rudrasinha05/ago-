/** Explicit user-triggered mutations. The backend remains the authority. */
import { safe, uuid, resource, validateProfile } from "./core.js";

function fieldHTML(field) {
  const name = safe(field.name);
  const label = '<label class="field-label" for="dlg-' + name + '">' +
    safe(field.label) + "</label>";
  const attrs = ' id="dlg-' + name + '" name="' + name + '"' +
    (field.required === false ? "" : " required") +
    (field.maxLength ? ' maxlength="' + Number(field.maxLength) + '"' : "") +
    (field.min !== undefined ? ' min="' + Number(field.min) + '"' : "") +
    (field.max !== undefined ? ' max="' + Number(field.max) + '"' : "");
  if (field.type === "select") {
    const choices = (field.options || []).map(option =>
      '<option value="' + safe(option.value) + '"' +
      (String(option.value) === String(field.value ?? "") ? " selected" : "") +
      '>' + safe(option.label) + "</option>").join("");
    return label + '<select' + attrs + ">" + choices + "</select>";
  }
  if (field.type === "textarea") {
    return label + '<textarea' + attrs + ' placeholder="' +
      safe(field.placeholder || "") + '">' + safe(field.value || "") +
      "</textarea>";
  }
  const type = ["text","email","number","datetime-local"].includes(field.type)
    ? field.type : "text";
  return label + '<input type="' + type + '"' + attrs +
    ' placeholder="' + safe(field.placeholder || "") + '" value="' +
    safe(field.value ?? "") + '">';
}

function openDialog(ctx, {
  title, description = "", fields = [], button = "Confirm",
  danger = false, onSubmit = async () => {}, refresh = true,
}) {
  const dialog = ctx.dialog;
  const host = document.getElementById("dialog-content");
  host.innerHTML = '<div class="dialog-head"><h2 id="dialog-title">' +
    safe(title) + '</h2><button type="button" data-modal-close ' +
    'class="icon-button" aria-label="Close dialog">' +
    '<svg class="ico" aria-hidden="true"><use href="#i-close"></use></svg>' +
    '</button></div><p>' + safe(description) +
    '</p><form id="operation-form">' + fields.map(fieldHTML).join("") +
    '<p id="operation-error" class="form-error" role="alert" hidden></p>' +
    '<div class="dialog-actions"><button class="btn btn-soft" type="button" ' +
    'data-modal-close>Cancel</button><button class="btn ' +
    (danger ? "btn-danger" : "btn-primary") +
    '" type="submit" id="operation-submit">' + safe(button) +
    "</button></div></form>";
  const form = document.getElementById("operation-form");
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const submit = document.getElementById("operation-submit");
    const errorBox = document.getElementById("operation-error");
    submit.disabled = true;
    errorBox.hidden = true;
    const values = Object.fromEntries(new FormData(form));
    try {
      const message = await onSubmit(values);
      dialog.close();
      ctx.toast(typeof message === "string" ? message : "Action completed.");
      if (refresh) await ctx.refreshCurrent();
    } catch (error) {
      // Render errors using textContent to avoid reflecting untrusted SQL/API strings.
      errorBox.textContent = String(error?.message || "Action could not be completed");
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
    }
  });
  if (dialog.open) dialog.close();
  dialog.showModal();
  host.querySelector("input,select,textarea,#operation-submit")?.focus();
}
function choose(value, label) {
  return { value: String(value), label: String(label) };
}
async function departmentsAndPeople(ctx) {
  const departments = await ctx.api.request("/v1/organization/departments");
  const teams = await Promise.all(departments.map(async department => {
    const members = await ctx.api.request(
      "/v1/organization/employees?department_id=" +
      encodeURIComponent(uuid(department.id)),
    );
    return members.map(employee => ({
      ...employee, department_name: department.name,
    }));
  }));
  return { departments, people: teams.flat() };
}
function choices(items, label = x => x.title || x.name || x.id) {
  return items.map(x => choose(uuid(x.id), label(x)));
}
function mustHave(items, message) {
  if (!items.length) throw new Error(message);
}
function confirmation(ctx, title, description, request, label = "Confirm") {
  openDialog(ctx, { title, description, button:label, onSubmit:request });
}
async function reviewApproval(ctx, id, initial = "approved") {
  id = uuid(id);
  const approvals = resource(ctx.state.data, "approvals");
  const request = Array.isArray(approvals) ? approvals.find(x => x.id === id) : null;
  if (request?.requester_id === ctx.state.me?.id) {
    throw new Error("The requester cannot review their own approval.");
  }
  openDialog(ctx, {
    title: "Independent approval decision",
    description: "Your decision is immutable. Approve only after personally reviewing the requested action.",
    button: "Record decision",
    fields: [
      { name:"decision",label:"Decision",type:"select",options:[
        choose("approved","Approve request"),choose("rejected","Reject request"),
      ],value:initial },
      { name:"reason",label:"Review rationale",type:"textarea",
        maxLength:3000,placeholder:"Explain your independent review…" },
    ],
    onSubmit: async values => {
      await ctx.api.request("/v1/governance/approvals/" + id + "/decision", {
        method:"POST",body:{
          approve:values.decision==="approved",reason:values.reason,
        },
      });
      return "Human approval decision recorded.";
    },
  });
}
async function planSteps(ctx, id) {
  id = uuid(id);
  const steps = await ctx.api.request("/v1/brain/plans/" + id + "/steps");
  openDialog(ctx, {
    title:"Plan steps",
    description:steps.length ? "Steps are recorded in the existing plan DAG." :
      "No steps yet. Add a step before submitting.",
    button:"Close",refresh:false,
    fields:[],
    onSubmit:async()=> "Plan viewed.",
  });
  const area=document.querySelector("#operation-form");
  if (Array.isArray(steps) && steps.length) {
    const list=document.createElement("div");
    list.className="row-list";
    steps.forEach(step=>{
      const item=document.createElement("div");
      item.className="keyval";
      const name=document.createElement("span");
      name.textContent=String(step.action);
      const order=document.createElement("strong");
      order.textContent="#"+step.position;
      item.append(name,order);
      list.appendChild(item);
    });
    area.prepend(list);
  }
}
export async function handleAction(key, id, ctx) {
  const { api, state, can } = ctx;
  if (key === "go-twin") { await ctx.goPage("twin"); return; }
  if (key === "refresh") { await ctx.refreshCurrent(); return; }
  if (["approve","reject","review-approval"].includes(key)) {
    await reviewApproval(ctx,id,key==="reject"?"rejected":"approved");
    return;
  }
  if (key === "new-goal") {
    const existing = resource(state.data,"goals") || [];
    openDialog(ctx,{
      title:"Create strategic goal",
      description:"A goal starts as an active strategic objective. No actions execute automatically.",
      button:"Create goal",
      fields:[
        {name:"title",label:"Goal title",maxLength:250,placeholder:"Example: Improve research capacity"},
        {name:"description",label:"Context",type:"textarea",required:false,maxLength:6000},
        {name:"parent_id",label:"Parent goal (optional)",type:"select",required:false,
          options:[choose("","Top-level goal"),...existing.filter(x=>x.status==="active")
            .map(x=>choose(x.id,x.title))]},
      ],
      onSubmit:async v=>{
        await api.request("/v1/brain/goals",{method:"POST",body:{
          title:v.title,description:v.description,parent_id:v.parent_id||null,
        }});
        return "Strategic objective created.";
      },
    });
    return;
  }
  if (key === "new-plan") {
    const goals=(resource(state.data,"goals")||[]).filter(x=>x.status==="active");
    mustHave(goals,"An active goal is required before creating a plan.");
    openDialog(ctx,{
      title:"Draft execution plan",
      description:"Draft plans require steps, independent approval and explicit activation.",
      button:"Create draft",
      fields:[
        {name:"goal_id",label:"Active parent goal",type:"select",
          options:choices(goals,x=>x.title)},
        {name:"title",label:"Plan name",maxLength:250,
          placeholder:"Example: 30-day operational roadmap"},
      ],
      onSubmit:async v=>{
        await api.request("/v1/brain/plans",{method:"POST",body:v});
        return "Draft plan created. Add steps before submission.";
      },
    });
    return;
  }
  if (key === "plan-steps") { await planSteps(ctx,id);return; }
  if (key === "plan-add-step") {
    id=uuid(id);
    const { people }=await departmentsAndPeople(ctx);
    mustHave(people,"Create an employee before assigning a plan step.");
    const steps=await api.request("/v1/brain/plans/"+id+"/steps");
    openDialog(ctx,{
      title:"Add governed plan step",
      description:"Assign an existing employee. Only draft plans can be changed.",
      button:"Add step",
      fields:[
        {name:"action",label:"Governed action identifier",maxLength:500,
          placeholder:"Example: internal:brief"},
        {name:"assignee_id",label:"Assigned employee",type:"select",
          options:choices(people,x=>x.name+" — "+x.department_name+" ("+x.kind+")")},
        {name:"depends_on",label:"Prerequisite step",type:"select",required:false,
          options:[choose("","None"),...steps.map(x=>choose(x.id,"#"+x.position+" "+x.action))]},
      ],
      onSubmit:async v=>{
        await api.request("/v1/brain/plans/"+id+"/steps",{method:"POST",
          body:{action:v.action,assignee_id:v.assignee_id,
            depends_on:v.depends_on||null}});
        return "Step recorded in draft plan.";
      },
    });
    return;
  }
  if (["plan-submit","plan-activate","plan-materialize"].includes(key)) {
    id=uuid(id);
    const operations={
      "plan-submit":["Submit plan for approval",
        "Human review is required before activation. This submission cannot be edited.",
        "/submit","Plan submitted for independent approval."],
      "plan-activate":["Activate approved plan",
        "Only an already independently approved strategy can be activated.",
        "/activate","Approved strategy activated."],
      "plan-materialize":["Materialize governed tasks",
        "Tasks will be created from the approved plan. Each task still needs separate approval.",
        "/materialize","Governed task materialization completed."],
    };
    const [title,description,path,message]=operations[key];
    confirmation(ctx,title,description,async()=>{
      await api.request("/v1/brain/plans/"+id+path,{method:"POST"});
      return message;
    });
    return;
  }
  if (key === "new-motion") {
    openDialog(ctx,{
      title:"Propose executive council motion",
      description:"At least two independent authorized human votes and M2 approval are required.",
      button:"Submit motion",
      fields:[
        {name:"title",label:"Motion title",maxLength:250},
        {name:"rationale",label:"Rationale",type:"textarea",maxLength:6000},
        {name:"required_votes",label:"Required independent voters",type:"number",
          min:2,max:10,value:2},
      ],
      onSubmit:async v=>{
        await api.request("/v1/council/motions",{method:"POST",
          body:{title:v.title,rationale:v.rationale,required_votes:Number(v.required_votes)}});
        return "Council motion proposed. Approval remains separate.";
      },
    });
    return;
  }
  if (key === "council-vote") {
    id=uuid(id);
    openDialog(ctx,{
      title:"Independent council vote",
      description:"The proposer cannot vote. One immutable ballot per authorized human.",
      button:"Submit vote",
      fields:[
        {name:"vote",label:"Position",type:"select",
          options:[choose("yes","Vote yes"),choose("no","Vote no")]},
        {name:"reason",label:"Rationale",type:"textarea",maxLength:3000},
      ],
      onSubmit:async v=>{
        await api.request("/v1/council/motions/"+id+"/votes",{method:"POST",body:v});
        return "Independent council ballot recorded.";
      },
    });
    return;
  }
  if (key === "council-finalize") {
    id=uuid(id);
    confirmation(ctx,"Finalize council motion",
      "Finalization requires quorum and distinct M2 human consent. Passing is advisory only.",
      async()=>{
        const out=await api.request("/v1/council/motions/"+id+"/finalize",
          {method:"POST"});
        return "Council motion finalized as "+out.status+". No execution authorized.";
      });
    return;
  }
  if (key === "new-department") {
    openDialog(ctx,{
      title:"Add department",description:"Creates an organizational department in this tenant.",
      button:"Create department",
      fields:[{name:"name",label:"Department name",maxLength:150}],
      onSubmit:async v=>{
        await api.request("/v1/organization/departments",{method:"POST",body:v});
        return "Department created.";
      },
    });
    return;
  }
  if (key === "new-ai") {
    const departments=resource(state.data,"departments")||[];
    mustHave(departments,"Create a department before adding an AI employee.");
    openDialog(ctx,{
      title:"Register an AI employee",
      description:"Registers a virtual employee record. It does not automatically execute a job.",
      button:"Register AI employee",
      fields:[
        {name:"department_id",label:"Department",type:"select",
          options:choices(departments,x=>x.name)},
        {name:"name",label:"Employee name",maxLength:150},
      ],
      onSubmit:async v=>{
        await api.request("/v1/organization/employees",{
          method:"POST",body:{...v,kind:"ai"},
        });
        return "AI employee registered. Execution remains governed.";
      },
    });
    return;
  }
  if (key === "new-knowledge") {
    openDialog(ctx,{
      title:"Propose institutional knowledge",
      description:"All statements require a source reference and independent human review.",
      button:"Submit for review",
      fields:[
        {name:"kind",label:"Evidence type",type:"select",
          options:["fact","artifact","decision","policy"].map(x=>choose(x,x))},
        {name:"label",label:"Short title",maxLength:250},
        {name:"statement",label:"Statement or finding",type:"textarea",maxLength:12000},
        {name:"source_ref",label:"Source reference",maxLength:1000,
          placeholder:"Example: internal:artifact:report-123"},
      ],
      onSubmit:async v=>{
        await api.request("/v1/knowledge/nodes",{method:"POST",body:v});
        return "Knowledge proposed. Human verification pending.";
      },
    });
    return;
  }
  if (key === "knowledge-review") {
    id=uuid(id);
    openDialog(ctx,{
      title:"Review knowledge evidence",
      description:"Verification records independent source review, not universal factual truth.",
      button:"Record review",
      fields:[
        {name:"decision",label:"Review result",type:"select",
          options:[choose("approve","Verify source"),choose("reject","Reject proposal")]},
        {name:"note",label:"Evidence inspection notes",type:"textarea",maxLength:3000},
      ],
      onSubmit:async v=>{
        await api.request("/v1/knowledge/nodes/"+id+"/review",{
          method:"POST",body:{approve:v.decision==="approve",note:v.note},
        });
        return "Independent knowledge review recorded.";
      },
    });
    return;
  }
  if (key === "new-enrollment") {
    const catalog=await api.request("/v1/tools/catalog");
    openDialog(ctx,{
      title:"Request trusted tool enrollment",
      description:"Approval to enroll is separate from every task's execution approval.",
      button:"Request enrollment",
      fields:[
        {name:"code",label:"Registered read-only tool",type:"select",
          options:catalog.map(x=>choose(x.code,x.code+" — "+x.description))},
        {name:"rationale",label:"Business justification",type:"textarea",
          maxLength:3000},
      ],
      onSubmit:async v=>{
        await api.request("/v1/tools/enrollments",{method:"POST",
          body:{code:v.code,rationale:v.rationale}});
        return "Tool enrollment requested. Independent approval required.";
      },
    });
    return;
  }
  if (key === "tool-reconcile") {
    id=uuid(id);
    confirmation(ctx,"Reconcile enrollment decision",
      "Activation or rejection only follows the exact independent M2 approval.",
      async()=>{
        const result=await api.request(
          "/v1/tools/enrollments/"+id+"/reconcile",{method:"POST"});
        return "Tool enrollment is now "+result.status+".";
      });
    return;
  }
  if (key === "tool-disable") {
    id=uuid(id);
    openDialog(ctx,{
      title:"Disable active tool enrollment",
      description:"Disabling the tool prevents subsequent dispatch and rule scans.",
      button:"Disable enrollment",danger:true,
      fields:[{name:"reason",label:"Operator reason",type:"textarea",maxLength:3000}],
      onSubmit:async v=>{
        await api.request("/v1/tools/enrollments/"+id+"/disable",{
          method:"POST",body:v,
        });
        return "Tool disabled for this tenant.";
      },
    });
    return;
  }
  if (key === "new-rule") {
    const { departments, people }=await departmentsAndPeople(ctx);
    const agents=people.filter(x=>x.kind==="ai");
    const active=(resource(state.data,"enrollments")||[])
      .filter(x=>x.status==="active");
    mustHave(departments,"No departments available.");
    mustHave(agents,"An AI employee is required before creating a rule.");
    mustHave(active,"Activate an independently approved tool first.");
    openDialog(ctx,{
      title:"New department automation",
      description:"Only verified source events create pending, independently approved tasks.",
      button:"Create rule",
      fields:[
        {name:"department_id",label:"Department",type:"select",
          options:choices(departments,x=>x.name)},
        {name:"assignee_id",label:"AI employee",type:"select",
          options:choices(agents,x=>x.name+" — "+x.department_name)},
        {name:"code",label:"Active tool",type:"select",
          options:active.map(x=>choose(x.tool_code,x.tool_code))},
        {name:"trigger",label:"Verified event source",type:"select",
          options:[choose("knowledge_verified","Knowledge independently verified"),
            choose("qa_pass","Task completed with passing independent QA")]},
      ],
      onSubmit:async v=>{
        await api.request("/v1/tools/automation/rules",{
          method:"POST",body:v,
        });
        return "Automation rule created; no task has executed.";
      },
    });
    return;
  }
  if (key === "automation-scan") {
    confirmation(ctx,"Scan for verified events",
      "This scan can create proposed tasks and approval requests. It cannot run tools.",
      async()=>{
        const result=await api.request("/v1/tools/automation/scan",{
          method:"POST",body:{limit:25},
        });
        return String(result.firings.length)+" pending task(s) created. No execution occurred.";
      },"Scan and propose tasks");
    return;
  }
  if (key === "rule-disable") {
    id=uuid(id);
    confirmation(ctx,"Disable automation rule",
      "Disabled rules cannot create new tasks. Prior audit remains immutable.",
      async()=>{
        await api.request("/v1/tools/automation/rules/"+id+"/disable",{
          method:"POST",
        });
        return "Rule disabled.";
      },"Disable rule");
    return;
  }
  if (key === "tool-run") {
    id=uuid(id);
    confirmation(ctx,"Dispatch approved read-only tool",
      "This action uses the independent per-task M2 approval and active tool enrollment. The run is single-use and must be independently reviewed.",
      async()=>{
        await api.request("/v1/tools/tasks/"+id+"/run",{method:"POST",
          timeoutMs:20000});
        return "Tool completed; independent QA remains required.";
      },"Execute once");
    return;
  }
  if (key === "new-event") {
    let invitees=[];
    try { invitees=(await departmentsAndPeople(ctx)).people; } catch { /* Scheduling without invitees remains possible. */ }
    const start=new Date(Date.now()+3600_000);
    const end=new Date(Date.now()+7200_000);
    const toLocal=x=>{
      const shifted=new Date(x.getTime()-x.getTimezoneOffset()*60000);
      return shifted.toISOString().slice(0,16);
    };
    openDialog(ctx,{
      title:"Schedule organizational event",
      description:"This creates an AGO internal record. No email or external invitation is sent.",
      button:"Schedule event",
      fields:[
        {name:"title",label:"Event title",maxLength:250},
        {name:"detail",label:"Details",type:"textarea",required:false,maxLength:6000},
        {name:"starts_at",label:"Starts (local time)",type:"datetime-local",
          value:toLocal(start)},
        {name:"ends_at",label:"Ends (local time)",type:"datetime-local",
          value:toLocal(end)},
        {name:"visibility",label:"Visibility",type:"select",
          options:[choose("tenant","Organization"),choose("private","Private to creator")]},
        {name:"employee_id",label:"Optional internal invitee",type:"select",required:false,
          options:[choose("","No attendee"),...invitees.map(x=>choose(x.id,x.name+" — "+x.department_name))]},
      ],
      onSubmit:async v=>{
        if (!globalThis.crypto?.randomUUID) {
          throw new Error("HTTPS or localhost is required to create secure event IDs.");
        }
        const startValue=new Date(v.starts_at),endValue=new Date(v.ends_at);
        if (!Number.isFinite(startValue.valueOf()) ||
          !Number.isFinite(endValue.valueOf())) throw new Error("Valid times required");
        await api.request("/v1/operations/calendar",{
          method:"POST",body:{
            title:v.title,detail:v.detail,visibility:v.visibility,
            starts_at:startValue.toISOString(),ends_at:endValue.toISOString(),
            operation_key:crypto.randomUUID(),
            employee_ids:v.employee_id ? [uuid(v.employee_id)] : [],
          },
        });
        return "Internal event scheduled.";
      },
    });
    return;
  }
  if (key === "calendar-cancel") {
    id=uuid(id);
    confirmation(ctx,"Cancel organizational event",
      "The creator may cancel a scheduled event. The event history is retained.",
      async()=>{
        await api.request("/v1/operations/calendar/"+id+"/cancel",{method:"POST"});
        return "Event cancelled.";
      },"Cancel event");
    return;
  }
  if (key === "calendar-rsvp") {
    id=uuid(id);
    openDialog(ctx,{
      title:"Respond to event",
      description:"Only invited employees may respond to a scheduled event.",
      button:"Save response",
      fields:[{name:"response",label:"My response",type:"select",
        options:[choose("accepted","Accept"),choose("declined","Decline")]}],
      onSubmit:async v=>{
        await api.request("/v1/operations/calendar/"+id+"/rsvp",{
          method:"POST",body:v,
        });
        return "Event response recorded.";
      },
    });
    return;
  }
  if (['reconcile-dna','reconcile-evaluation','reconcile-recommendation'].includes(key)) {
    const folder={'reconcile-dna':'dna','reconcile-evaluation':'evaluations','reconcile-recommendation':'recommendations'}[key];
    confirmation(ctx,'Finalize independent review','The matching human approval must already be decided in Governance.',async()=>{
      const out=await api.request('/v1/meta/'+folder+'/'+uuid(id)+'/reconcile',{method:'POST'});
      return 'Review finalized: '+out.status;
    });return;
  }
  if (key === 'propose-company-dna' || key === 'propose-scoped-dna') {
    const scoped=key==='propose-scoped-dna', active=resource(state.data,'dna');
    const charters=scoped?['communication_style','documentation_philosophy','meeting_philosophy','learning_philosophy']:Object.keys(active?.charter || {});
    const targets=scoped?await departmentsAndPeople(ctx):null;
    const options=targets?[...targets.departments.map(d=>choose('department:'+d.id,'Department: '+d.name)),...targets.people.map(e=>choose('employee:'+e.id,'Employee: '+e.name))]:[];
    if(scoped)mustHave(options,'Create a department or employee first.');
    openDialog(ctx,{title:scoped?'Propose inherited guidance':'Propose company culture',description:'Creates a version for independent human review. Child thresholds must preserve or strengthen the parent. These words never grant permissions.',button:'Submit for review',fields:[
      ...(scoped?[{name:'target',label:'Scope',type:'select',options}]:[]),
      ...['qa_target_pct','backlog_limit','budget_alert_pct'].map(name=>({name,label:name.replaceAll('_',' '),type:'number',value:active?.profile?.[name],min:name==='backlog_limit'?0:name==='qa_target_pct'?50:1,max:name==='backlog_limit'?10000:100})),
      ...charters.map(name=>({name,label:name.replaceAll('_',' '),type:'textarea',maxLength:2000,value:active?.charter?.[name]})),
      {name:'rationale',label:'Why should this change?',type:'textarea',maxLength:3000}],onSubmit:async v=>{
        const [scope_kind,scope_id]=scoped?v.target.split(':'):['company',null];
        const profile=validateProfile(Object.fromEntries(['qa_target_pct','backlog_limit','budget_alert_pct'].map(k=>[k,Number(v[k])])));
        await api.request('/v1/meta/dna',{method:'POST',body:{profile,charter:Object.fromEntries(charters.map(k=>[k,v[k]])),scope_kind,scope_id,rationale:v.rationale}});
        return 'DNA proposal recorded. Ask an independent reviewer to decide in Governance.';
      }});return;
  }
  if(key==='inspect-dna') {
    const {people}=await departmentsAndPeople(ctx);mustHave(people,'Create an employee first.');
    openDialog(ctx,{title:'Inspect inherited DNA',description:'Reads company, department and employee guidance.',refresh:false,fields:[{name:'employee',label:'Employee',type:'select',options:choices(people,x=>x.name)}],onSubmit:async v=>{
      const out=await api.request('/v1/meta/dna/effective?employee_id='+uuid(v.employee));
      return 'Inherited '+out.lineage.map(x=>x.scope+' v'+(x.version??'default')).join(' → ')+'. Quality target: '+out.profile.qa_target_pct+'%. Mission: '+out.charter.mission;
    }});return;
  }
  if(key==='propose-evaluation') {
    const recs=(resource(state.data,'recommendations')||[]).filter(x=>x.status==='endorsed'), snaps=resource(state.data,'snapshots')||[];
    mustHave(recs,'Independently endorse a recommendation first.');mustHave(snaps,'Capture later evidence first.');
    openDialog(ctx,{title:'Evaluate an observed change',description:'Compare the original evidence with a later snapshot. Independent review validates the observation; it does not establish causation.',button:'Submit comparison',fields:[
      {name:'recommendation',label:'Endorsed recommendation',type:'select',options:choices(recs,x=>x.summary)},
      {name:'after',label:'Later evidence',type:'select',options:choices(snaps,x=>String(x.created_at))},
      {name:'evidence',label:'What actually changed?',type:'textarea',maxLength:3000}],onSubmit:async v=>{
        await api.request('/v1/meta/evaluations',{method:'POST',body:{recommendation_id:uuid(v.recommendation),after_id:uuid(v.after),change_evidence:v.evidence}});
        return 'Observed comparison recorded for independent review.';
      }});return;
  }
  if (key === "capture-snapshot") {
    confirmation(ctx,"Capture live executive evidence",
      "Create an immutable M7 snapshot from existing tenant tasks, QA and virtual credits. This does not produce a prediction or execute any work.",
      async()=>{
        const result=await api.request("/v1/meta/snapshots",{method:"POST"});
        state.twin.snapshotId=result.id;
        state.twin.simulation=null;
        return "Executive evidence captured.";
      },"Capture evidence");
    return;
  }
  if (key === "compare-twin") {
    const selected=state.twin.snapshotId ||
      (resource(state.data,"snapshots")||[])[0]?.id;
    if (!selected) throw new Error("Capture evidence first before running a Digital Twin scenario.");
    const profile=validateProfile(state.twin.profile ||
      resource(state.data,"dna")?.profile);
    const result=await api.request("/v1/meta/simulate",{
      method:"POST",body:{snapshot_id:uuid(selected),profile},
    });
    state.twin.simulation=result;
    ctx.showPage();
    ctx.toast("Scenario evaluated. No changes were applied to AGO.");
    return;
  }
  if (key === "reset-twin") {
    const approved=resource(state.data,"dna");
    state.twin.profile={...approved?.profile ||
      {qa_target_pct:85,backlog_limit:5,budget_alert_pct:80}};
    state.twin.simulation=null;
    ctx.showPage();
    return;
  }
  if (key === "verify-snapshot") {
    const selected=state.twin.snapshotId ||
      (resource(state.data,"snapshots")||[])[0]?.id;
    if (!selected) throw new Error("No recorded evidence to verify.");
    const result=await api.request("/v1/meta/snapshots/"+uuid(selected)+"/verify");
    ctx.toast(result.verified ? "Source fingerprint verified." :
      "Evidence fingerprint mismatch. Investigate the original records.",
    !result.verified);
    return;
  }
  if (key === "generate-recommendations") {
    const selected=state.twin.snapshotId ||
      (resource(state.data,"snapshots")||[])[0]?.id;
    if (!selected) throw new Error("Record an executive snapshot first.");
    confirmation(ctx,"Propose Meta Brain recommendations",
      "This may create immutable advisory proposals and human approval requests. Nothing is endorsed, executed or applied automatically.",
      async()=>{
        const proposals=await api.request(
          "/v1/meta/snapshots/"+uuid(selected)+"/recommendations",{
            method:"POST",
          });
        return String(proposals.length)+" advisory proposal(s) recorded. Human decisions remain pending.";
      },"Generate proposals");
    return;
  }
  if (key === "task-request-approval") {
    id=uuid(id);
    confirmation(ctx,"Request independent task approval",
      "Create one exact M2 approval for this proposed task. It cannot execute until another authorized human approves.",
      async()=>{
        const out=await api.request(
          "/v1/console/tasks/"+id+"/request-approval",{method:"POST"});
        return "Approval request "+out.approval_id.slice(0,8)+"… created.";
      },"Request review");
    return;
  }
  if (key === "agent-run") {
    id=uuid(id);
    confirmation(ctx,"Run approved AI employee task",
      "Only an independently approved task with a registered handler can execute. The output requires separate human QA.",
      async()=>{
        const out=await api.request("/v1/agents/tasks/"+id+"/run",{
          method:"POST",timeoutMs:20000,
        });
        return out.status==="completed" ?
          "AI task completed; independent QA is now required." : "AI task status: "+out.status;
      },"Run approved AI");
    return;
  }
  if (key === "qa-review") {
    id=uuid(id);
    openDialog(ctx,{
      title:"Independent QA outcome",
      description:"Review the completed task's actual evidence. This verdict is immutable and cannot be submitted by its executor.",
      button:"Record QA verdict",
      fields:[
        {name:"verdict",label:"Quality verdict",type:"select",
          options:[choose("pass","Pass"),choose("fail","Fail")]},
        {name:"evidence",label:"Review evidence and rationale",type:"textarea",
          maxLength:5000,placeholder:"Describe what was inspected and why…"},
      ],
      onSubmit:async v=>{
        await api.request("/v1/tasks/"+id+"/review",{method:"POST",body:v});
        return "Independent QA verdict recorded.";
      },
    });
    return;
  }
  throw new Error("The requested action is not supported.");
}
