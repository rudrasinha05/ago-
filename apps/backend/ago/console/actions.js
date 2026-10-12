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
  if (field.type === "file") {
    return label+'<input type="file"'+attrs+' accept=".pdf,.txt,.md,.csv,.json,.png,.jpg,.jpeg">';
  }
  if (["select","multiselect"].includes(field.type)) {
    const choices = (field.options || []).map(option =>
      '<option value="' + safe(option.value) + '"' +
      (String(option.value) === String(field.value ?? "") ? " selected" : "") +
      '>' + safe(option.label) + "</option>").join("");
    return label + '<select' + attrs + (field.type==="multiselect"?' multiple size="4"':"") + ">" + choices + "</select>";
  }
  if (field.type === "textarea") {
    return label + '<textarea' + attrs + ' placeholder="' +
      safe(field.placeholder || "") + '">' + safe(field.value || "") +
      "</textarea>";
  }
  const type = ["text","email","number","datetime-local"].includes(field.type)
    ? field.type : "text";
  return label + '<input type="' + type + '"' + attrs + (type==="number"?' step="any"':"") +
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
    const formData = new FormData(form);
    const values = Object.fromEntries(formData);
    for(const field of fields)if(field.type==="multiselect")values[field.name]=formData.getAll(field.name);
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
  let details = null;
  if(request?.action?.startsWith("enterprise:review:")) {
    details=await ctx.api.request("/v1/enterprise/reviews/source/"+id);
    if(!details?.digest)throw new Error("Exact source unavailable; review cancelled.");
  } else if(request?.action?.startsWith("enterprise:")) {
    details=await ctx.api.request("/v1/operations/enterprise/approval-details/"+id);
    if(details?.details?.content_base64) {
      if(["text/plain","text/markdown","application/json"].includes(details.details.content_type)) {
        details.details.text_content=new TextDecoder().decode(Uint8Array.from(atob(details.details.content_base64),x=>x.charCodeAt(0)));
      }
      delete details.details.content_base64;
    }
  }
  if(request?.action?.startsWith("calendar:review:")) {
    details=await ctx.api.request("/v1/operations/calendar/governance/approvals/"+id);
    if(!details?.digest || !details?.source)throw new Error("Exact calendar source package unavailable; review cancelled.");
  }
  if(request?.action?.startsWith("constitution:")) {
    const c=await ctx.api.request("/v1/governance/constitution");
    details=(c.proposals || []).find(x=>Object.values(x.reviews || {}).includes(id)) || (c.emergency_reviews || []).find(x=>x.approval_id===id);
    if(!details)throw new Error("Exact constitutional source package unavailable; review cancelled.");
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
  if(details) appendEvidence(document.getElementById("operation-form"),details);
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
  if(key.startsWith("batch-"))return batchAction(key,id,ctx);
  if(key.startsWith("constitution-"))return constitutionalAction(key,id,ctx);
  const { api, state, can } = ctx;
  if (key.startsWith("enterprise-")) { await enterpriseAction(key,id,ctx); return; }
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
  if (key.startsWith("calendar-governed-")) {
    await calendarGovernedAction(ctx,key,id);
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

const enterpriseBase = "/v1/operations/enterprise";
const newOperation = () => crypto.randomUUID();
const textField = (name,label,maxLength=1500) => ({name,label,type:"textarea",maxLength});
const selectField = (name,label,options,required=true) => ({name,label,type:"select",options,required});
const numericField = (name,label,value=0,max=1000000) => ({name,label,type:"number",min:0,max,value});
const timeField = (name,label,value="") => ({name,label,type:"datetime-local",value});
const instant = value => value ? new Date(value).toISOString() : null;
export function evidencePreview(value) {
  const result=structuredClone(value);
  const visit=item=>{
    if(!item || typeof item!=="object")return;
    if(item.content_base64) {
      try {
        const bytes=Uint8Array.from(atob(item.content_base64),x=>x.charCodeAt(0));
        try {item.document_text=new TextDecoder("utf-8",{fatal:true}).decode(bytes);}
        catch {item.document_text="Binary source: download the exact document to inspect before deciding.";}
      } catch {item.document_text="Invalid source bytes: do not approve this document.";}
      delete item.content_base64;
    }
    for(const child of Object.values(item))visit(child);
  };visit(result);
  return result;
}
function appendEvidence(host,value) {
  const pre=document.createElement("pre");pre.textContent=JSON.stringify(evidencePreview(value),null,2);
  pre.style.cssText="white-space:pre-wrap;overflow-wrap:anywhere;max-height:55vh;overflow:auto";
  host.prepend(pre);
  const item=value.details || value;
  if(item.payload?.content_base64) {
    const button=document.createElement("button");button.type="button";button.className="btn btn-soft";
    button.textContent="Download exact source document";
    button.addEventListener("click",()=>{
      const bytes=Uint8Array.from(atob(item.payload.content_base64),x=>x.charCodeAt(0));
      const pdf=String.fromCharCode(...bytes.slice(0,5))==="%PDF-";
      const url=URL.createObjectURL(new Blob([bytes],{type:pdf?"application/pdf":"application/octet-stream"}));
      const link=document.createElement("a");link.href=url;link.download=pdf?"review-source.pdf":"review-source.bin";
      link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
    });host.prepend(button);
  }
}
function showEvidence(ctx,title,value) {
  openDialog(ctx,{title,description:"Recorded source evidence. Review assumptions and scope before deciding.",
    refresh:false,button:"Close",onSubmit:async()=>"Evidence viewed."});
  appendEvidence(document.getElementById("operation-form"),value);
}
async function enterpriseAction(key,id,ctx) {
  const {api,state,can}=ctx;
  const records=resource(state.data,"enterpriseEvidence") || [];
  const post=async(path,body={})=>api.request(enterpriseBase+path,{method:"POST",body});
  if(key==="enterprise-evidence") {
    const record=records.find(x=>x.id===uuid(id));
    if(!record)throw new Error("Refresh to load the current evidence.");
    showEvidence(ctx,"Evidence and provenance",record);return;
  }
  if(key==="enterprise-apply-intent") {
    confirmation(ctx,"Apply reviewed operation","This applies exactly the saved parameters. The server rechecks independent approval.",
      async()=>{await post("/intents/"+uuid(id)+"/apply");return "Reviewed operation applied.";});return;
  }
  if(key==="enterprise-review-evidence") {
    const record=records.find(x=>x.id===uuid(id));
    if(!record)throw new Error("Evidence missing.");
    const approvals=resource(state.data,"approvals") || [];
    const action="enterprise:evidence:"+record.id+":"+record.digest;
    const approved=approvals.find(x=>x.action===action && x.status==="approved" && x.requester_id===state.me.id);
    confirmation(ctx,"Evidence review",approved?"Record the independent decision against this exact evidence digest.":
      "Create an independent human review request. Review does not authenticate provider invoices or apply changes.",async()=>{
        if(approved)await post("/evidence/"+record.id+"/review",{approval_id:approved.id});
        else await post("/evidence/"+record.id+"/approval");
        return approved?"Independent evidence review recorded.":"Review requested. Open Governance with the independent reviewer.";
      });return;
  }
  if(key==="enterprise-apply-hr") {
    const intents=resource(state.data,"enterpriseOrgIntents") || [];
    const intent=intents.find(x=>x.id===uuid(id));
    if(!intent)throw new Error("Recorded HR intent missing.");
    confirmation(ctx,"Apply reviewed organization change","The exact saved request will be applied after the server verifies independent approval.",
      async()=>{await post("/organization/apply",{...intent.payload,approval_id:intent.approval_id});return "Organization change applied.";});return;
  }
  if(key==="enterprise-agent-intent" || key==="enterprise-apply-agent") {
    const item=(resource(state.data,"enterpriseAgentIntents") || []).find(x=>x.id===uuid(id));
    if(!item)throw new Error("Saved employee evidence request missing.");
    if(key==="enterprise-agent-intent") {showEvidence(ctx,"Reported employee evidence",item);return;}
    confirmation(ctx,"Record reviewed employee evidence","This records the exact reviewed claim. Confidence stays uncalibrated and grants no authority.",async()=>{
      await post("/agents/"+item.employee_id+"/evidence/"+item.id+"/apply",{approval_id:item.approval_id});
      return "Reviewed reported evidence recorded.";
    });return;
  }
  if(key==="enterprise-apply-revision") {
    const item=(resource(state.data,"enterpriseRevisions") || []).find(x=>x.id===uuid(id));
    if(!item)throw new Error("Revision intent missing.");
    confirmation(ctx,"Apply reviewed revision","The original plan stays immutable. Descendant boundaries and stale versions are checked.",async()=>{
      await post("/plans/"+item.horizon_plan_id+"/revisions/"+item.id+"/apply",{approval_id:item.approval_id});return "Reviewed revision applied.";
    });return;
  }
  if(key==="enterprise-claim") {
    confirmation(ctx,"Run one approved offline task","Only an independently approved internal task is eligible. Separate human QA follows execution.",async()=>{
      const claim=await post("/work-queue/offline-claim",{lease_seconds:600});
      if(!claim.queue_id)return "No safe approved offline task is available.";
      await post("/work-queue/"+claim.queue_id+"/run",{lease_id:claim.lease_id});
      return "Offline task completed. Independent QA is pending.";
    });return;
  }
  if(key==="enterprise-asset-view" || key==="enterprise-asset-impact") {
    const path=key==="enterprise-asset-view"?"/payload":"/impact";
    const result=await api.request(enterpriseBase+"/marketplace/"+uuid(id)+path);
    if(result.content_base64 && result.content_type!=="application/octet-stream") {
      result.text_preview=new TextDecoder().decode(Uint8Array.from(atob(result.content_base64),x=>x.charCodeAt(0)));
      delete result.content_base64;
    }
    showEvidence(ctx,key==="enterprise-asset-view"?"Approved reusable content":"Version sunset and dependency impact",result);return;
  }
  if(key==="enterprise-publish") {
    const asset=(resource(state.data,"enterpriseAssets") || []).find(x=>x.id===uuid(id));
    const request=(resource(state.data,"approvals") || []).find(x=>x.action==="enterprise:publish:"+id && x.status==="approved" && x.requester_id===state.me.id);
    confirmation(ctx,"Publish internal asset",request?"Publish the reviewed payload and exact version.":"Request independent review of stored content and dependency manifest.",async()=>{
      if(request)await post("/marketplace/"+asset.id+"/publish");
      else await post("/marketplace/"+asset.id+"/approval");
      return request?"Asset published.":"Publication review requested.";
    });return;
  }
  if(key!=="enterprise-command")throw new Error("Unknown enterprise action.");
  if(!can("organization:manage"))throw new Error("Organization management permission required.");
  openDialog(ctx,{title:"Organization operations",description:"Choose a workflow. Changes require independent review; evidence captures are read-only observations.",
    fields:[selectField("command","Workflow",[
      choose("cycle","Capture operating lifecycle"),choose("lifecycle","Advance durable lifecycle phase"),choose("hr","Hire / promote / retire / department change"),
      choose("mode","Company / department operating mode"),choose("worker","AI availability / pause / sleep / resume"),
      choose("capacity","Execution capacity"),choose("assessment","Assess AI competence from actual QA"),
      choose("agent-state","Inspect employee state and autonomy boundaries"),choose("agent-evidence","Propose reported skills / confidence / learning evidence"),
      choose("help","Request assistance / refuse unsafe work"),choose("resolve","Resolve reviewed assistance"),
      choose("plan","Create approved planning horizon"),choose("rollup","Capture planning feedback and conflicts"),
      choose("replan","Propose a versioned plan revision"),choose("plan-link","Link an approved task to a horizon"),
      choose("enqueue","Queue independently approved work"),choose("budget","Cost envelope"),
      choose("cost","Record observed cost / revenue"),choose("finance","Assess cost / ROI assumptions"),choose("financial-document","Import invoice / bank source"),choose("reconcile","Reconcile reviewed financial sources"),
      choose("asset","Store reusable asset draft"),choose("consume","Request approved asset reuse"),
      choose("retire","Deprecate / revoke an asset"),choose("diagnostics","Capture evolution diagnostics"),
      choose("experiment","Compare real reviewed task cohorts"),choose("register-experiment","Register future packet experiment"),choose("measure-experiment","Measure registered experiment"),choose("policy-audit","Audit approved capacity change / rollback"),choose("twin-state","Capture organizational Twin state"),
      choose("forecast","Freeze a task quality forecast"),choose("calibrate","Measure later forecast outcomes"),
      choose("economic-period","Measure reconciled economic period"),choose("economic-study","Register future cost improvement"),choose("economic-comparison","Compare observed ROI / cost / QA"),
      choose("quality-subject","Store exact quality subject version"),choose("quality-study","Register rubric quality comparison"),choose("quality-sample","Record source-backed quality scores"),choose("quality-report","Measure reviewed quality comparison"),
      choose("metric-outcome","Record actual business outcome"),choose("longitudinal-forecast","Freeze business prediction / interval"),choose("longitudinal-calibration","Measure prediction accuracy over time"),
    ])],button:"Continue",refresh:false,onSubmit:async v=>{
      // Close the chooser before opening the next native modal.
      ctx.dialog.close();setTimeout(()=>enterpriseForm(v.command,ctx).catch(e=>ctx.toast(e.message)),0);
      return "Workflow selected.";
    }});
}
async function enterpriseForm(command,ctx) {
  if(["economic-period","economic-study","economic-comparison","quality-subject","quality-study","quality-sample","quality-report","metric-outcome","longitudinal-forecast","longitudinal-calibration"].includes(command))return measurementForm(command,ctx);
  const {api,state}=ctx;
  const base=enterpriseBase;
  const post=(path,body)=>api.request(base+path,{method:"POST",body});
  if(command==="lifecycle") {
    confirmation(ctx,"Advance organization lifecycle","Advance one durable phase with source evidence. Offline execution remains opt-in through the local operator command.",async()=>{
      const status=await api.request(base+"/lifecycle");
      const result=await post("/lifecycle/advance",{operation_key:newOperation(),expected_event_id:status.checkpoint?.id || null,execute_one:false});
      return "Lifecycle phase: "+result.payload.phase;
    });return;
  }
  if(["cycle","diagnostics","twin-state"].includes(command)) {
    const path={cycle:"/cycle",diagnostics:"/evolution/diagnostics","twin-state":"/twin/state"}[command];
    confirmation(ctx,"Capture source evidence","Save current observed records and their immutable digest.",async()=>{
      await post(path,{operation_key:newOperation()});return "Source evidence captured.";
    });return;
  }
  const {departments,people}=await departmentsAndPeople(ctx);
  const ai=people.filter(x=>x.kind==="ai");
  const evidence=resource(state.data,"enterpriseEvidence") || [];
  const plans=resource(state.data,"enterprisePlans") || [];
  const assets=resource(state.data,"enterpriseAssets") || [];
  const tasks=resource(state.data,"tasks") || [];
  const approvalIds=new Set((resource(state.data,"approvals") || []).filter(x=>x.status==="approved").map(x=>x.id));
  const approvedTasks=tasks.filter(t=>t.status==="waiting_approval" && approvalIds.has(t.approval_id));
  const entity=(name,label,rows)=>selectField(name,label,choices(rows));
  const note=textField("reason","Reason / review rationale");
  let fields=[], submit;
  const intent=async(operation,target_id,parameters)=>{
    await post("/intents",{operation,target_id,parameters});
    return "Exact operation saved. Independent reviewer can inspect it in Operations and decide in Governance.";
  };
  if(command==="hr") {
    fields=[selectField("change_kind","Change",[choose("created","Create department"),choose("hired","Hire AI employee"),choose("promoted","Promote AI employee"),choose("terminated","Terminate AI employee"),choose("closed","Close department")]),
      selectField("target_id","Existing target (promotion / termination / closure)",[choose("","Creating new target"),...choices([...ai,...departments])],false),
      {name:"name",label:"New department / employee name",required:false,maxLength:200},
      selectField("department_id","Hiring department",[choose("","Not hiring"),...choices(departments)],false),numericField("role_level","Promotion level (2–5)",2,5),note];
    submit=async v=>{
      const creating=["created","hired"].includes(v.change_kind);
      const payload={change_kind:v.change_kind,target_id:creating?newOperation():v.target_id,reason:v.reason};
      if(creating)payload.name=v.name;
      if(v.change_kind==="hired")payload.department_id=v.department_id;
      if(v.change_kind==="promoted")payload.role_level=Number(v.role_level);
      await post("/organization/approval",payload);return "Exact HR review request saved.";
    };
  } else if(command==="mode" || command==="capacity" || command==="budget") {
    fields=[selectField("scope_kind","Scope",[choose("company","Company"),choose("department","Department"),choose("employee","AI employee")]),
      selectField("scope_id","Scope target (company leaves blank)",[choose("","Company"),...choices([...departments,...ai])],false)];
    if(command==="mode")fields.push(selectField("target","Operating mode",["active","paused","maintenance","emergency","suspended"].map(x=>choose(x,x))),timeField("expires_at","Expires at"),note);
    if(command==="capacity")fields.push(numericField("max_running","Maximum concurrent tasks",1,1000),note);
    if(command==="budget")fields.push(numericField("ceiling","Observed-currency ceiling",0),{name:"currency",label:"Currency",value:"INR",maxLength:3});
    submit=async v=>{
      const params={scope_kind:v.scope_kind,scope_id:v.scope_kind==="company"?null:v.scope_id};
      if(command==="mode")Object.assign(params,{target:v.target,expires_at:instant(v.expires_at),rationale:v.reason});
      if(command==="capacity")Object.assign(params,{max_running:Number(v.max_running),rationale:v.reason});
      if(command==="budget")Object.assign(params,{ceiling:v.ceiling,currency:v.currency});
      return intent(command,null,params);
    };
  } else if(command==="agent-state") {
    mustHave(ai,"Create an AI employee first.");
    openDialog(ctx,{title:"Employee state",description:"Inspect actual assignments, dependencies and permission boundaries.",fields:[entity("employee_id","AI employee",ai)],button:"Inspect",refresh:false,onSubmit:async v=>{
      const [state,autonomy]=await Promise.all([api.request(base+"/agents/"+v.employee_id+"/state"),api.request(base+"/agents/"+v.employee_id+"/autonomy")]);
      setTimeout(()=>showEvidence(ctx,"Operational employee state",{state,autonomy}),0);
      return "Employee state loaded.";
    }});return;
  } else if(command==="agent-evidence") {
    mustHave(ai,"Create an AI employee first.");
    fields=[entity("employee_id","AI employee",ai),selectField("kind","Evidence category",["skill","knowledge","confidence","risk","learning","permission_awareness"].map(x=>choose(x,x))),{name:"label",label:"Evidence label",maxLength:160},numericField("value_int","Reported confidence (only for confidence)",50,100),textField("evidence_ref","Source reference",1024),textField("note","Reviewed observation",2000)];
    submit=async v=>{
      await post("/agents/"+v.employee_id+"/evidence/approval",{kind:v.kind,label:v.label,value_int:v.kind==="confidence"?Number(v.value_int):null,evidence_ref:v.evidence_ref,note:v.note});
      return "Exact employee evidence saved for independent review. Claims do not grant permissions or establish mastery.";
    };
  } else if(command==="worker" || command==="assessment") {
    mustHave(ai,"Create an AI employee first.");fields=[entity("employee_id","AI employee",ai)];
    if(command==="worker")fields.push(selectField("state","Availability",["available","idle","paused","sleeping","interrupted","unavailable"].map(x=>choose(x,x))),{...timeField("expires_at","Restriction expiry (required for temporary pause/sleep/interrupt)"),required:false},note);
    submit=async v=>command==="assessment"?(await post("/agents/"+v.employee_id+"/assessment",{operation_key:newOperation()}),"Actual QA assessment saved."):
      intent("worker",v.employee_id,{state:v.state,reason:v.reason,expires_at:instant(v.expires_at)});
  } else if(command==="help" || command==="resolve") {
    if(command==="help") {
      fields=[entity("employee_id","AI employee",ai),selectField("reason","Reason",["overload","low_confidence","missing_permission","dependency","safety_risk","assistance"].map(x=>choose(x,x))),
        selectField("severity","Severity",[choose("blocking","Block execution"),choose("advisory","Advisory")]),textField("summary","Help needed"),textField("evidence_ref","Evidence source",1024)];
      submit=async v=>{await post("/assistance",v);return "Assistance requested; blockers affect scheduling.";};
    } else {
      const requests=(resource(state.data,"enterpriseAssistance") || []).filter(x=>x.outcome!=="resolved");
      mustHave(requests,"No open assistance requests.");
      fields=[entity("request_id","Assistance request",requests),selectField("outcome","Outcome",[choose("resolved","Resolved"),choose("rejected","Rejected; remains blocked")]),textField("explanation","Resolution evidence")];
      submit=v=>intent("resolve",v.request_id,{outcome:v.outcome,explanation:v.explanation});
    }
  } else if(command==="plan" || command==="replan" || command==="rollup" || command==="plan-link") {
    if(command==="rollup") {
      mustHave(plans,"Create an approved horizon plan first.");fields=[entity("plan_id","Plan / hierarchy root",plans)];
      submit=async v=>{await post("/plans/"+v.plan_id+"/rollup",{operation_key:newOperation()});return "Plan lineage, QA and conflicts captured.";};
    } else if(command==="plan-link") {
      fields=[entity("plan_id","Approved horizon",plans),entity("task_id","Approved governed task",approvedTasks),textField("evidence_ref","Strategy lineage evidence",1024)];
      submit=v=>intent("link",null,{horizon_plan_id:v.plan_id,task_id:v.task_id,evidence_ref:v.evidence_ref});
    } else {
      fields=command==="plan"?[selectField("horizon","Planning horizon",["lifetime","five_year","annual","quarterly","monthly","weekly","daily","hourly","current_task"].map(x=>choose(x,x))),selectField("parent_id","Approved parent",[choose("","Lifetime root"),...choices(plans)],false)]:[entity("plan_id","Plan to revise",plans)];
      fields.push({name:"title",label:"Plan title",maxLength:300},timeField("starts_at","Starts at"),timeField("ends_at","Ends at"),numericField("budget_ceiling","Virtual-credit ceiling"),textField("evidence_ref","Source evidence",1024));
      if(command==="replan")fields.push(textField("rationale","Why this revision is needed"));
      submit=async v=>{
        const params={title:v.title,starts_at:instant(v.starts_at),ends_at:instant(v.ends_at),budget_ceiling:v.budget_ceiling,evidence_ref:v.evidence_ref};
        if(command==="plan")return intent("plan",null,{...params,horizon:v.horizon,parent_id:v.parent_id||null});
        const original=plans.find(x=>x.id===v.plan_id);
        await post("/plans/"+v.plan_id+"/revisions/approval",{...params,base_revision:original.revision,rationale:v.rationale});
        return "Immutable revision review requested. Apply its saved row after independent approval.";
      };
    }
  } else if(command==="enqueue") {
    mustHave(approvedTasks,"An independently approved task awaiting execution is required.");
    fields=[entity("task_id","Approved task",approvedTasks),numericField("priority","Priority (0–100)",50,100)];
    submit=async v=>{await post("/work-queue",{task_id:v.task_id,priority:Number(v.priority),operation_key:"queue:"+v.task_id,eligible_at:new Date().toISOString()});return "Approved task queued.";};
  } else if(command==="cost") {
    fields=[selectField("category","Observed category",["model","storage","tool","execution","time","revenue","other"].map(x=>choose(x,x))),
      {name:"provider",label:"Provider / payer",maxLength:180},textField("source_ref","Actual source reference",1024),numericField("amount","Observed amount"),{name:"currency",label:"Currency",value:"INR",maxLength:3},timeField("period_start","Period starts"),timeField("period_end","Period ends")];
    submit=async v=>{await post("/costs",{...v,operation_key:newOperation(),period_start:instant(v.period_start),period_end:instant(v.period_end)});return "Observed financial claim saved; provider verification pending.";};
  } else if(command==="finance") {
    const costs=resource(state.data,"enterpriseCosts") || [];mustHave(costs,"Record actual cost/revenue claims first.");
    fields=[{name:"currency",label:"Analyze currency",value:"INR",maxLength:3},numericField("baseline_revenue","Baseline revenue assumption"),numericField("alternative_net","Alternative net benefit assumption"),textField("assumptions","Baseline, comparison period and limitations")];
    submit=async v=>{await post("/finance/assessment",{...v,cost_ids:costs.filter(x=>x.currency===v.currency).map(x=>x.id),operation_key:newOperation()});return "Financial assessment saved with explicit assumptions.";};
  } else if(command==="asset") {
    fields=[entity("department_id","Publisher department",departments),{name:"name",label:"Asset name",maxLength:200},selectField("kind","Asset type",["service","library","dataset","research","design_system","template","agent","model","workflow"].map(x=>choose(x,x))),{name:"version",label:"Version",value:"1.0.0",maxLength:30},{name:"license_id",label:"License / reuse terms",maxLength:200},textField("content","Reusable text content",500000),{...textField("manifest","JSON compatibility manifest",16000),value:'{"dependencies":[]}'}];
    submit=async v=>{
      const bytes=new TextEncoder().encode(v.content);
      const hash=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),x=>x.toString(16).padStart(2,"0")).join("");
      let raw="";for(const byte of bytes)raw+=String.fromCharCode(byte);
      const asset=await post("/marketplace",{department_id:v.department_id,name:v.name,kind:v.kind,version:v.version,license_id:v.license_id,sha256_digest:hash,manifest:JSON.parse(v.manifest)});
      await post("/marketplace/"+asset.id+"/payload",{content_type:"text/plain",content_base64:btoa(raw)});
      return "Content stored in draft. Request independent publication review from the asset row.";
    };
  } else if(command==="consume" || command==="retire") {
    const published=assets.filter(x=>x.status==="published");mustHave(published,"A published internal asset is required.");
    fields=[entity("asset_id","Published asset",published)];
    if(command==="consume")fields.push(entity("department_id","Consumer department",departments),textField("evidence_ref","Reuse purpose / evidence",1024));
    else fields.push(selectField("target_state","Retirement",[choose("deprecated","Deprecate version"),choose("revoked","Revoke asset")]),note);
    submit=v=>intent(command,v.asset_id,command==="consume"?{department_id:v.department_id,evidence_ref:v.evidence_ref}:{target_state:v.target_state,reason:v.reason});
  } else if(command==="forecast") {
    const snapshots=evidence.filter(x=>x.kind==="twin_state");mustHave(snapshots,"Capture organizational Twin state first.");
    fields=[entity("snapshot_id","Frozen organizational state",snapshots),timeField("horizon_end","Observation window ends")];
    submit=async v=>{
      const snapshot=snapshots.find(x=>x.id===v.snapshot_id);
      const ids=snapshot.payload.tasks.filter(t=>!t.verdict && !["completed","failed"].includes(t.status)).map(t=>t.id);
      if(!ids.length)throw new Error("This snapshot has no unfinished forecast cohort.");
      await post("/twin/forecast",{snapshot_id:v.snapshot_id,task_ids:ids,horizon_end:instant(v.horizon_end),operation_key:newOperation()});return "Forecast frozen before future QA outcomes.";
    };
  } else if(command==="calibrate") {
    const forecasts=evidence.filter(x=>x.kind==="forecast");mustHave(forecasts,"Freeze a forecast before measuring later observations.");
    fields=[entity("forecast_id","Frozen forecast",forecasts)];
    submit=async v=>{await post("/twin/forecasts/"+v.forecast_id+"/calibrate",{operation_key:newOperation()});return "Later outcomes measured; pending observations remain explicit.";};
  } else if(command==="register-experiment") {
    const eligible=tasks.filter(x=>["proposed","waiting_approval"].includes(x.status));
    mustHave(eligible,"At least two future internal tasks for the same employee are required.");
    fields=[textField("task_ids","Future task UUIDs, comma separated",6000),textField("seed","Frozen assignment seed",160),textField("hypothesis","Packet layout hypothesis"),textField("rollback_plan","Rollback / retain baseline")];
    submit=async v=>{await post("/evolution/register",{task_ids:v.task_ids.split(",").map(x=>uuid(x.trim())),seed:v.seed,hypothesis:v.hypothesis,rollback_plan:v.rollback_plan,operation_key:newOperation()});return "Prospective packet variants registered. Independent evidence review required before task execution.";};
  } else if(command==="measure-experiment") {
    const registered=evidence.filter(x=>x.kind==="experiment_registration");mustHave(registered,"Register a future experiment first.");
    fields=[entity("registration_id","Registered experiment",registered)];
    submit=async v=>{await post("/evolution/registrations/"+v.registration_id+"/measure",{operation_key:newOperation()});return "Later actual packet outputs and independent QA measured; missing outcomes remain pending.";};
  } else if(command==="policy-audit") {
    const proposals=evidence.filter(x=>["diagnostics","experiment_measurement"].includes(x.kind) && x.reviewed_at);
    const results=new Set(evidence.filter(x=>x.kind==="intent_result").map(x=>x.operation_key));
    const applied=evidence.filter(x=>x.kind==="intent" && x.payload.operation==="capacity" && results.has(x.id)).map(x=>({...x,name:"Capacity "+x.payload.parameters.max_running+" · "+x.id.slice(0,8)}));
    mustHave(proposals,"Independently review a diagnostics or experiment source first.");mustHave(applied,"Apply independently approved baseline, candidate and rollback capacities through Operations first.");
    fields=[entity("proposal_id","Reviewed evolution source",proposals),entity("baseline_intent_id","Actual baseline capacity",applied),entity("candidate_intent_id","Actual candidate capacity",applied),entity("rollback_intent_id","Actual restored baseline capacity",applied)];
    submit=async v=>{await post("/evolution/policy-audit",{...v,operation_key:newOperation()});return "Actual reviewed capacity applications and exact baseline restoration audited. Evolution applied no change.";};
  } else if(command==="financial-document") {
    const costs=resource(state.data,"enterpriseCosts") || [];mustHave(costs,"Record the corresponding cost / revenue claim first.");
    fields=[entity("cost_id","Cost / revenue claim",costs),selectField("document_type","Source type",[choose("invoice","Invoice / revenue record"),choose("bank","Bank transaction record")]),{name:"source_file",label:"Exact invoice / bank document (up to 200KB)",type:"file",required:false},{...textField("content","Or paste exact source text",180000),required:false}];
    submit=async v=>{const file=v.source_file;if(file?.size>200000)throw new Error("Source document must be at most 200KB.");const bytes=file?.size?new Uint8Array(await file.arrayBuffer()):new TextEncoder().encode(v.content || "");let raw="";for(const byte of bytes)raw+=String.fromCharCode(byte);await post("/finance/documents",{cost_id:v.cost_id,document_type:v.document_type,content_base64:btoa(raw),operation_key:newOperation()});return "Exact source bytes stored. Request independent evidence review before reconciliation.";};
  } else if(command==="reconcile") {
    const documents=evidence.filter(x=>x.kind==="financial_document" && x.reviewed_at);
    const invoices=documents.filter(x=>x.payload.document_type==="invoice"),banks=documents.filter(x=>x.payload.document_type==="bank");
    mustHave(invoices,"An independently reviewed invoice is required.");mustHave(banks,"An independently reviewed bank source is required.");
    fields=[entity("invoice_id","Reviewed invoice",invoices),entity("bank_id","Reviewed bank source",banks),{name:"currency",label:"Currency",value:"INR",maxLength:3},numericField("baseline_revenue","Assumed baseline revenue",0,1000000000),numericField("alternative_net","Assumed alternative net",0,1000000000),textField("assumptions","Period / baseline assumptions")];
    submit=async v=>{await post("/finance/reconcile",{matches:[{invoice_id:v.invoice_id,bank_id:v.bank_id}],currency:v.currency,baseline_revenue:String(v.baseline_revenue),alternative_net:String(v.alternative_net),assumptions:v.assumptions,operation_key:newOperation()});return "Reviewed invoice/bank evidence reconciled. Provider authentication remains dependent on genuine records.";};
  } else if(command==="experiment") {
    const reviewed=tasks.filter(x=>["completed","failed"].includes(x.status));mustHave(reviewed,"Two independently QA-reviewed task cohorts are required.");
    fields=[entity("baseline_id","Baseline reviewed task",reviewed),entity("candidate_id","Candidate reviewed task",reviewed),textField("hypothesis","Improvement hypothesis"),textField("rollback_plan","Rollback proposal")];
    submit=async v=>{await post("/evolution/experiment",{baseline_task_ids:[v.baseline_id],candidate_task_ids:[v.candidate_id],hypothesis:v.hypothesis,rollback_plan:v.rollback_plan,operation_key:newOperation()});return "Source-verified comparison captured; independent proposal review required.";};
  } else throw new Error("Workflow unavailable.");
  openDialog(ctx,{title:"Organization · "+command.replaceAll("-"," "),description:"Saved operations retain source evidence and require the applicable independent review.",
    fields,button:"Save workflow",onSubmit:submit});
}

async function sourceBase64(values) {
  const file=values.source_file;
  if(file?.size>200000)throw new Error("Source must be at most 200KB.");
  const bytes=file?.size?new Uint8Array(await file.arrayBuffer()):new TextEncoder().encode(values.content || "");
  if(!bytes.length)throw new Error("Attach the exact source file or paste its actual text.");
  let raw="";for(const byte of bytes)raw+=String.fromCharCode(byte);return btoa(raw);
}
const sourceFields=()=>[{name:"source_file",label:"Exact source file (up to 200KB)",type:"file",required:false},
  {...textField("content","Or paste exact actual source text",180000),required:false}];
const periodFields=()=>[timeField("period_start","Period starts"),timeField("period_end","Period ends")];
const seriesFields=()=>[selectField("dimension","Outcome dimension",["cost","revenue","growth","market","risk","headcount"].map(x=>choose(x,x))),
  textField("metric","Stable metric: total_cost, total_revenue, expense category, or customer count",160),{name:"unit",label:"Unit: currency, count, percent or probability",value:"INR",maxLength:160},
  {name:"entity_ref",label:"Organization / measured entity",value:"company",maxLength:160}];
const seriesValue=v=>({dimension:v.dimension,metric:v.metric,unit:v.unit,entity_ref:v.entity_ref});
async function measurementForm(command,ctx) {
  const post=body=>ctx.api.request(enterpriseBase+"/measurements/"+command,{method:"POST",body:{...body,operation_key:newOperation()}});
  const load=async kind=>(await ctx.api.request(enterpriseBase+"/evidence?kind="+encodeURIComponent(kind))).map(x=>({...x,name:
    [x.kind,x.payload?.dimension,x.payload?.version,x.payload?.period_start,x.id.slice(0,8)].filter(Boolean).join(" · ")}));
  const reviewed=async kind=>(await load(kind)).filter(x=>x.reviewed_at);
  const select=(name,label,rows,optional=false)=>selectField(name,label,[...(optional?[choose("","None / unknown")]:[]),...choices(rows)],!optional);
  let fields=[],submit;
  if(command==="economic-period") {
    const matches=await reviewed("reconciliation");mustHave(matches,"Independently review reconciliations first.");
    const budgets=resource(ctx.state.data,"enterpriseBudgets") || [],tasks=resource(ctx.state.data,"tasks") || [];
    fields=[{...select("reconciliation_ids","Reviewed reconciliations (select all sources)",matches),type:"multiselect"},
      {name:"currency",label:"Currency",value:"INR",maxLength:3},...periodFields(),
      {...select("task_ids","QA task cohort (optional; selected outputs form the denominator)",tasks.filter(t=>["completed","failed"].includes(t.status)),true),type:"multiselect"},
      select("budget_id","Approved company envelope",budgets.filter(b=>b.scope_kind==="company"),true),textField("assumptions","Period allocation, completeness and business context")];
    submit=async v=>{await post({...v,task_ids:v.task_ids.filter(Boolean),budget_id:v.budget_id||null,period_start:instant(v.period_start),period_end:instant(v.period_end)});return "Observed period saved. Missing categories / QA / budget remain explicit; request independent review.";};
  } else if(command==="economic-study") {
    const periods=await reviewed("economic_period");mustHave(periods,"Independently review a baseline economic period first.");
    const results=new Set((await load("intent_result")).map(x=>x.operation_key));
    const changes=(await load("intent")).filter(x=>!results.has(x.id));mustHave(changes,"Save a governed change request before applying it, then register its measurement study.");
    fields=[select("baseline_period_id","Observed baseline",periods),...periodFields(),select("change_ref","Exact saved, unapplied change request",changes),textField("hypothesis","Expected measured benefit"),textField("rollback_plan","How to restore the baseline")];
    submit=async v=>{await post({...v,period_start:instant(v.period_start),period_end:instant(v.period_end)});return "Future intervention registered. Independently review it before the candidate period starts.";};
  } else if(command==="economic-comparison") {
    const periods=await reviewed("economic_period"),studies=await reviewed("economic_study");mustHave(periods,"Review observed economic periods first.");
    const changes=[...await reviewed("intent_result"),...await reviewed("evolution_policy_audit")];
    fields=[select("baseline_period_id","Observed baseline",periods),select("candidate_period_id","Later observed candidate",periods),select("alternative_period_id","Observed alternative (optional)",periods,true),
      select("study_id","Prospective improvement study (optional)",studies,true),select("change_evidence_id","Actual independently reviewed change (required for a study)",changes,true),textField("assumptions","Comparable workload, value, risks and period allocation")];
    submit=async v=>{for(const key of ["alternative_period_id","study_id","change_evidence_id"])v[key]=v[key]||null;await post(v);return "Observed ROI, opportunity cost and safeguards saved. Recommendations require human review.";};
  } else if(command==="quality-subject") {
    fields=[selectField("dimension","Quality dimension",["prompt","architecture","workflow","department","employee"].map(x=>choose(x,x))),
      textField("entity_ref","Stable subject name (department/employee: existing entity ID)",160),{name:"version",label:"Immutable version",value:"1.0",maxLength:80},textField("source_ref","Original subject source reference",1024),...sourceFields()];
    submit=async v=>{await post({dimension:v.dimension,entity_ref:v.entity_ref,version:v.version,source_ref:v.source_ref,content_base64:await sourceBase64(v)});return "Exact version stored. Independently review its source before enrollment.";};
  } else if(command==="quality-study") {
    const subjects=await reviewed("quality_subject");mustHave(subjects,"Review two distinct versions of the same subject first.");
    fields=[select("baseline_subject_id","Reviewed baseline version",subjects),select("candidate_subject_id","Reviewed candidate version",subjects),
      {name:"metric_name",label:"Rubric criterion 1",value:"correctness",maxLength:80},numericField("weight","Criterion 1 weight",1,100),
      {name:"metric_name_2",label:"Rubric criterion 2",value:"safety",maxLength:80},numericField("weight_2","Criterion 2 weight",1,100),
      numericField("expected_per_variant","Predeclared samples per version",5,100),textField("sampling_plan","How samples are selected fairly and comparably"),textField("hypothesis","Expected improvement"),textField("rollback_plan","Retain / restore baseline")];
    submit=async v=>{await post({baseline_subject_id:v.baseline_subject_id,candidate_subject_id:v.candidate_subject_id,rubric:[{name:v.metric_name,maximum:"100",weight:v.weight},{name:v.metric_name_2,maximum:"100",weight:v.weight_2}],expected_per_variant:Number(v.expected_per_variant),sampling_plan:v.sampling_plan,hypothesis:v.hypothesis,rollback_plan:v.rollback_plan});return "Rubric and sample quotas frozen. Independent review required before recording samples.";};
  } else if(command==="quality-sample") {
    const studies=await reviewed("quality_study");mustHave(studies,"Independently review a rubric study first.");
    openDialog(ctx,{title:"Select reviewed quality study",fields:[select("study_id","Frozen study",studies)],button:"Continue",refresh:false,onSubmit:async v=>{
      ctx.dialog.close();setTimeout(()=>qualityScoreForm(ctx,studies.find(x=>x.id===v.study_id)).catch(e=>ctx.toast(e.message)),0);return "Study selected.";
    }});return;
  } else if(command==="quality-report") {
    const studies=await reviewed("quality_study");mustHave(studies,"Review a rubric study first.");fields=[select("study_id","Frozen quality study",studies)];
    submit=async v=>{await post(v);return "Reviewed rubric scores compared. Pending samples and uncertainty remain visible.";};
  } else if(command==="metric-outcome") {
    const periods=await reviewed("economic_period");
    fields=[...seriesFields(),...periodFields(),{...numericField("value","Measured value (nonfinancial only)"),required:false,value:"",min:-1000000000},
      select("economic_period_id","Reviewed economic period (cost / revenue only)",periods,true),textField("source_ref","Actual source reference",1024),textField("methodology","How this exact-period value was measured"),...sourceFields()];
    submit=async v=>{const financial=["cost","revenue"].includes(v.dimension);await post({series:seriesValue(v),period_start:instant(v.period_start),period_end:instant(v.period_end),value:financial?null:v.value,economic_period_id:financial?v.economic_period_id||null:null,content_base64:financial?null:await sourceBase64(v),source_ref:v.source_ref,methodology:v.methodology});return "Actual outcome saved. Independent source review required before calibration.";};
  } else if(command==="longitudinal-forecast") {
    const snapshots=await load("twin_state");mustHave(snapshots,"Capture a complete Twin state first.");
    fields=[select("snapshot_id","Frozen organizational state",snapshots),{name:"model_version",label:"Stable prediction model version",value:"owner-scenario-v1",maxLength:160},...seriesFields(),...periodFields(),
      {...numericField("predicted_value","Predicted value"),min:-1000000000},{...numericField("lower","Lower uncertainty bound"),min:-1000000000},{...numericField("upper","Upper uncertainty bound"),min:-1000000000},
      textField("interval_basis","How the uncertainty interval was obtained"),textField("assumptions","Prediction assumptions"),textField("sensitivity_factors","Factors that could change the outcome")];
    submit=async v=>{await post({snapshot_id:v.snapshot_id,model_version:v.model_version,predictions:[{series:seriesValue(v),period_start:instant(v.period_start),period_end:instant(v.period_end),predicted_value:v.predicted_value,lower:v.lower,upper:v.upper,interval_basis:v.interval_basis}],assumptions:v.assumptions,sensitivity_factors:v.sensitivity_factors});return "Future prediction frozen. Independently review it before the target period starts.";};
  } else if(command==="longitudinal-calibration") {
    const forecasts=await reviewed("longitudinal_forecast");mustHave(forecasts,"Independently review future business forecasts first.");
    fields=[{...select("forecast_ids","Same-model forecasts across periods (select all)",forecasts),type:"multiselect"}];
    submit=async v=>{await post(v);return "Exact-period forecast errors and interval coverage measured. Missing/overdue actuals remain visible.";};
  }
  openDialog(ctx,{title:"Organization · "+command.replaceAll("-"," "),description:"Use actual source records. Saved measurements require independent review; forecasts and comparisons remain advisory.",fields,button:"Save measurement",onSubmit:submit});
}
async function qualityScoreForm(ctx,study) {
  const rubric=study.payload.rubric;
  const fields=[selectField("variant","Observed version",[choose("baseline","Baseline"),choose("candidate","Candidate")]),
    textField("sample_ref","Unique actual sample / output source",160),timeField("observed_at","When this sample was actually observed"),
    ...rubric.map((r,i)=>numericField("score_"+i,r.name+" score (0–"+r.maximum+")",0,Number(r.maximum))),textField("rationale","Evidence supporting these scores"),...sourceFields()];
  openDialog(ctx,{title:"Score exact quality sample",description:study.payload.sampling_plan,fields,button:"Save for independent review",onSubmit:async v=>{
    await ctx.api.request(enterpriseBase+"/measurements/quality-sample",{method:"POST",body:{operation_key:newOperation(),study_id:study.id,variant:v.variant,sample_ref:v.sample_ref,observed_at:instant(v.observed_at),scores:Object.fromEntries(rubric.map((r,i)=>[r.name,v["score_"+i]])),rationale:v.rationale,content_base64:await sourceBase64(v)}});
    return "Actual output and rubric scores saved. Independent review is required before measurement.";
  }});
}


async function constitutionalAction(key,id,ctx) {
  const base="/v1/governance/constitution", record=await ctx.api.request(base);
  const post=(path,body)=>ctx.api.request(base+path,{method:"POST",body});
  if(key==="constitution-view" || key==="constitution-incident") {
    const row=(key==="constitution-view"?record.proposals:record.emergencies)?.find(x=>x.id===uuid(id));
    if(!row)throw new Error("Constitutional record unavailable.");
    showEvidence(ctx,"Immutable constitutional record",row);return;
  }
  if(key==="constitution-adopt" || key==="constitution-close") {
    confirmation(ctx,key==="constitution-adopt"?"Adopt reviewed constitution":"Close reviewed emergency","The exact package must have independent human approval. Existing laws and audit remain enforced.",async()=>{
      await post(key==="constitution-adopt"?"/adopt":"/close-incident",key==="constitution-adopt"?{proposal_id:uuid(id)}:{review_id:uuid(id)});
      return "Constitutional decision recorded.";
    });return;
  }
  const contexts=["brain","meta","organization","tasks","agents","tools","knowledge","operations","council","memory","insights","calendar","messages"];
  const fields=[], text=(name,label)=>({name,label,type:"textarea",maxLength:3000});
  let submit;
  if(key==="constitution-propose") {
    const simulations=await ctx.api.request("/v1/operations/enterprise/twin");
    mustHave(simulations,"Capture executive evidence and run a Twin scenario first in Operations.");
    fields.push({name:"simulation_id",label:"Source Twin scenario",type:"select",options:choices(simulations,x=>"Scenario "+x.id)},
      {name:"operation_key",label:"Unique amendment reference",type:"text",maxLength:160},
      {name:"effective_at",label:"Earliest effective time",type:"datetime-local"},
      {name:"blocked_contexts",label:"Operations restricted by this version (optional)",type:"multiselect",required:false,options:contexts.map(x=>choose(x,x))},
      ...[["title","Amendment title"],["rationale","Why change?"],["risk","Impact and operational risk"],["affected_rights","Affected rights and authority"],["alternatives","Alternatives considered"],["dissent","Dissent and known uncertainty"],["rollback","Rollback procedure"],["monitoring","How will outcomes be reviewed?"],["propagation","Policy, DNA and workflow propagation plan"]].map(x=>text(...x)));
    submit=async v=>{
      const specification=Object.fromEntries(["title","rationale","risk","affected_rights","alternatives","dissent","rollback","monitoring","propagation","simulation_id","blocked_contexts"].map(x=>[x,v[x]]));
      await post("/proposals",{operation_key:v.operation_key,base_revision:record.active.revision,effective_at:new Date(v.effective_at).toISOString(),specification});
      return "Package saved with five independent review requests in Governance.";
    };
  } else if(key==="constitution-emergency") {
    fields.push({name:"operation_key",label:"Unique incident reference",type:"text",maxLength:160},
      {name:"blocked_contexts",label:"Immediately freeze these operations",type:"multiselect",options:contexts.map(x=>choose(x,x))},
      text("reason","Incident and reason"),text("containment","Containment and safe recovery plan"),
      {name:"expires_at",label:"Stop expires within 24 hours",type:"datetime-local"});
    submit=async v=>{await post("/emergencies",{...v,expires_at:new Date(v.expires_at).toISOString()});return "Containment active. Independent post-incident review is required.";};
  } else if(key==="constitution-review-incident") {
    fields.push(text("postmortem","What happened and what was learned?"),text("recovery_evidence","Actual recovery evidence"));
    submit=async v=>{await post("/incident-review",{emergency_id:uuid(id),...v});return "Recovery package saved for independent review in Governance.";};
  } else throw new Error("Unknown constitutional action.");
  openDialog(ctx,{title:key==="constitution-emergency"?"Emergency containment":"Constitutional evidence package",description:"Human authority, independent review and immutable audit remain active.",fields,button:key==="constitution-emergency"?"Freeze selected operations":"Submit evidence",danger:key==="constitution-emergency",onSubmit:submit});
}

async function calendarGovernedAction(ctx,key,id) {
  const gov=resource(ctx.state.data,"calendarGovernance");
  if(!gov || !Number.isInteger(gov.revision))throw new Error("Calendar source unavailable; refresh this workspace.");
  const base="/v1/operations/calendar";
  if(key==="calendar-governed-inspect") {
    const proposal=(gov.proposals || []).find(x=>x.id===uuid(id));
    if(!proposal)throw new Error("Calendar source package unavailable.");
    openDialog(ctx,{title:"Calendar source package",button:"Close",refresh:false});
    appendEvidence(document.getElementById("operation-form"),proposal);
    return;
  }
  if(key==="calendar-governed-apply") {
    const proposal=(gov.proposals || []).find(x=>x.id===uuid(id));
    if(!proposal || proposal.actor_id!==ctx.state.me?.id || proposal.status!=="approved")throw new Error("Original proposer and independent approved review required.");
    openDialog(ctx,{title:"Apply reviewed calendar change",description:"Apply this exact reviewed package. Changes to source events or the calendar revision require another review.",button:"Apply reviewed change",onSubmit:async()=>{
      await ctx.api.request(base+"/governance/apply",{method:"POST",body:{proposal_id:uuid(id)}});
      return "Reviewed calendar change applied.";
    }});
    appendEvidence(document.getElementById("operation-form"),proposal);
    return;
  }
  if(key==="calendar-governed-tick") {
    confirmation(ctx,"Observe due calendar cycles","Record due planning, budget, review and maintenance signals for human follow-up.",async()=>{
      await ctx.api.request(base+"/tick",{method:"POST"});
      return "Due cycle signals recorded; human business decisions remain required.";
    },"Record due signals");
    return;
  }
  const {departments,people}=await departmentsAndPeople(ctx);
  const scopeOptions=[choose("company","Company"),...departments.map(x=>choose("department:"+x.id,"Department · "+x.name)),...people.map(x=>choose("employee:"+x.id,"Employee · "+x.name))];
  const scopes=[{name:"scope",label:"Applies to",type:"select",options:scopeOptions}];
  const humans=people.filter(x=>x.kind==="human");
  const scope=v=>v.scope==="company"?{scope_kind:"company",scope_id:null}:{scope_kind:v.scope.split(":")[0],scope_id:uuid(v.scope.split(":")[1])};
  const rationales=[{name:"rationale",label:"Reason for this calendar change",type:"textarea",maxLength:6000}];
  const propose=async(command,specification,rationale)=>{
    await ctx.api.request(base+"/governance/proposals",{method:"POST",body:{command,specification,rationale,base_revision:gov.revision,operation_key:crypto.randomUUID()}});
    return "Calendar change proposed. Another authorized human must review the exact source in Governance.";
  };
  if(key==="calendar-governed-policy") {
    openDialog(ctx,{title:"Propose availability policy",description:"Company, department and employee policies combine. Quiet hours and holidays constrain task starts; they never grant approval authority.",button:"Submit for independent review",fields:[...scopes,
      {name:"timezone",label:"IANA time zone",value:"Asia/Kolkata",maxLength:100},
      {name:"weekdays",label:"Working days",type:"multiselect",options:["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map((x,i)=>choose(String(i),x)),value:"0"},
      {name:"start",label:"Working hours start (HH:MM)",value:"09:00"},
      {name:"end",label:"Working hours end (HH:MM)",value:"18:00"},
      {name:"quiet_start",label:"Quiet hours start (optional HH:MM)",required:false},
      {name:"quiet_end",label:"Quiet hours end (optional HH:MM)",required:false},
      {name:"region",label:"Holiday region",required:false,maxLength:120},
      {name:"holidays",label:"Holiday dates, one YYYY-MM-DD per line",type:"textarea",required:false,maxLength:5000},
      {name:"reviewer_ids",label:"Human supervisor coverage",type:"multiselect",required:false,options:humans.map(x=>choose(x.id,x.name))},
      {name:"require_supervisor",label:"Require an available human supervisor",type:"select",options:[choose("false","No additional calendar constraint"),choose("true","Require available authorized supervisor")]},
      {name:"emergency_reviewer_ids",label:"Emergency human review coverage",type:"multiselect",required:false,options:humans.map(x=>choose(x.id,x.name))},
      {name:"support_start",label:"Support coverage start (optional HH:MM)",required:false},
      {name:"support_end",label:"Support coverage end (optional HH:MM)",required:false},
      {name:"max_continuous_minutes",label:"Maximum continuous work in minutes",type:"number",min:1,max:1440,value:480},
      {name:"rest_minutes",label:"Rest between AI task runs in minutes",type:"number",min:0,max:1440,value:0},...rationales],
      onSubmit:async v=>propose("policy",{...scope(v),timezone:v.timezone,weekdays:v.weekdays.map(Number),start:v.start,end:v.end,
        quiet_start:v.quiet_start || null,quiet_end:v.quiet_end || null,region:v.region,
        holidays:v.holidays.split(/\s+/).filter(Boolean),reviewer_ids:v.reviewer_ids,emergency_reviewer_ids:v.emergency_reviewer_ids,
        require_supervisor:v.require_supervisor==="true",support_start:v.support_start || null,support_end:v.support_end || null,
        max_continuous_minutes:Number(v.max_continuous_minutes),rest_minutes:Number(v.rest_minutes)},v.rationale)});
    return;
  }
  const future=new Date(Date.now()+3600_000).toISOString();
  const later=new Date(Date.now()+7200_000).toISOString();
  if(key==="calendar-governed-window") {
    openDialog(ctx,{title:"Propose organizational cycle",description:"Select the responsible calendar domain and exact times with their UTC offset. Recurrence keeps local wall time; a daylight-saving ambiguity requires separate explicit windows.",button:"Submit for independent review",fields:[...scopes,
      {name:"kind",label:"Calendar domain",type:"select",options:Object.keys(gov.domains).map(x=>choose(x,x.replaceAll("_"," ")))},
      {name:"title",label:"Cycle or window title",maxLength:250},
      {name:"timezone",label:"IANA time zone",value:"UTC"},
      {name:"starts_at",label:"Starts with UTC offset",value:future},
      {name:"ends_at",label:"Ends with UTC offset",value:later},
      {name:"cadence",label:"Repeat",type:"select",options:["once","weekly","monthly","quarterly","annual","sprint"].map(x=>choose(x,x))},
      {name:"count",label:"Number of occurrences",type:"number",min:1,max:52,value:1},
      {name:"sprint_days",label:"Sprint length in days",type:"number",min:7,max:28,value:14},
      {name:"depends_on",label:"Must follow these windows",type:"multiselect",required:false,options:gov.windows.map(x=>choose(x.id,x.title))},
      {name:"parent_id",label:"Parent planning horizon",type:"select",required:false,options:[choose("","No parent"),...gov.windows.map(x=>choose(x.id,x.title))]},...rationales],
      onSubmit:async v=>propose("window",{...scope(v),kind:v.kind,title:v.title,timezone:v.timezone,starts_at:v.starts_at,ends_at:v.ends_at,
        cadence:v.cadence,count:Number(v.count),sprint_days:Number(v.sprint_days),depends_on:v.depends_on,parent_id:v.parent_id || null},v.rationale)});
    return;
  }
  const shared=listCalendarEvents(ctx).filter(x=>x.visibility==="tenant" && x.status==="scheduled");
  const eventFields=[{name:"event_id",label:"Shared event",type:"select",options:shared.map(x=>choose(x.id,x.title))}];
  if(key==="calendar-governed-cancel-window") {
    mustHave(gov.windows,"No active governed windows.");
    openDialog(ctx,{title:"Propose window cancellation",button:"Submit for independent review",fields:[
      {name:"window_id",label:"Active window",type:"select",options:gov.windows.map(x=>choose(x.id,x.title))},...rationales],
      onSubmit:async v=>propose("window_cancel",{window_id:uuid(v.window_id)},v.rationale)});
    return;
  }
  if(key==="calendar-governed-link") {
    mustHave(shared,"Create a shared event before linking deadlines.");
    const tasks=resource(ctx.state.data,"tasks") || [];
    openDialog(ctx,{title:"Propose event dependencies",description:"Task starts must fit their linked event. Each handoff follows its prerequisite; private events remain private.",button:"Submit for independent review",fields:[...eventFields,
      {name:"depends_on",label:"Prerequisite events",type:"multiselect",required:false,options:shared.map(x=>choose(x.id,x.title))},
      {name:"task_id",label:"Linked task deadline",type:"select",required:false,options:[choose("","No task"),...tasks.map(x=>choose(x.id,x.action+" · "+x.status))]},
      {name:"goal_id",label:"Optional goal ID",required:false},...rationales],
      onSubmit:async v=>propose("event_link",{event_id:uuid(v.event_id),depends_on:v.depends_on,task_id:v.task_id || null,goal_id:v.goal_id || null},v.rationale)});
    return;
  }
  if(key==="calendar-governed-reschedule") {
    mustHave(shared,"Create a shared event before rescheduling.");
    openDialog(ctx,{title:"Propose coordinated reschedule",description:"The exact change includes dependent events and deadline impacts. Original events remain in history; replacement invitations need fresh responses.",button:"Submit for independent review",fields:[...eventFields,
      {name:"starts_at",label:"New start with UTC offset",value:future},
      {name:"ends_at",label:"New end with UTC offset",value:later},...rationales],
      onSubmit:async v=>propose("reschedule",{event_id:uuid(v.event_id),starts_at:v.starts_at,ends_at:v.ends_at},v.rationale)});
    return;
  }
  if(key==="calendar-governed-eligibility") {
    mustHave(people,"No employees available.");
    openDialog(ctx,{title:"Check availability and deadline",button:"Check availability",refresh:false,fields:[
      {name:"employee_id",label:"Employee",type:"select",options:people.map(x=>choose(x.id,x.name))},
      {name:"at",label:"Proposed start with UTC offset",value:future},
      {name:"duration_minutes",label:"Reserved duration in minutes",type:"number",min:1,max:1440,value:30},
      {name:"task_id",label:"Optional task ID",required:false}],onSubmit:async v=>{
        const query=new URLSearchParams({employee_id:uuid(v.employee_id),at:v.at,duration_minutes:v.duration_minutes,search_days:"14"});
        if(v.task_id)query.set("task_id",uuid(v.task_id));
        const result=await ctx.api.request(base+"/eligibility?"+query);
        setTimeout(()=>{openDialog(ctx,{title:"Calendar eligibility result",button:"Close",refresh:false});appendEvidence(document.getElementById("operation-form"),result);},0);
        return result.eligible?"Reserved window is available; task approval remains required.":"Calendar constraints found.";
      }});
  }
}
function listCalendarEvents(ctx) { const value=resource(ctx.state.data,"events");return Array.isArray(value)?value:[]; }

async function batchAction(key,id,ctx) {
  const {api,state}=ctx;
  const post=(path,body={})=>api.request(path,{method:'POST',body});
  const choicesOf=items=>items.map(x=>choose(x,x.replaceAll('_',' ')));
  const text=(name,label,type='text',extra={})=>({name,label,type,...extra});
  const select=(name,label,items)=>text(name,label,'select',{options:choicesOf(items)});
  const display=(title,value)=>{openDialog(ctx,{title,description:'Source-linked result. Review evidence and limitations before acting.',button:'Close',refresh:false});const pre=document.createElement('pre');pre.textContent=JSON.stringify(value,null,2);document.getElementById('operation-form').prepend(pre);};
  const submit=async(domain,command,spec,rationale)=>{const revision=await api.request('/v1/enterprise/reviews/'+domain);await post('/v1/enterprise/reviews/'+domain+'/propose',{command,specification:spec,operation_key:crypto.randomUUID(),base_revision:revision.revision,rationale});return 'Saved for independent review in Governance.';};
  if(key==='batch-inspect' || key==='batch-apply') {
    const [domain,identifier]=id.split(':');if(!['graph','behavior','analytics','integration'].includes(domain))throw new Error('Unknown review domain.');
    const review=await api.request('/v1/enterprise/reviews/'+domain);const item=review.proposals.find(x=>x.id===uuid(identifier));if(!item)throw new Error('Source package not available.');
    if(key==='batch-inspect')return display('Exact reviewed source',item);
    return confirmation(ctx,'Apply reviewed change','Applies only the exact independently approved package.',async()=>{await post('/v1/enterprise/reviews/'+domain+'/apply',{proposal_id:identifier});return 'Reviewed change applied.';});
  }
  if(key==='batch-graph-sync'){await post('/v1/enterprise/graph/synchronize');await ctx.refreshCurrent();return;}
  if(key==='batch-analytics-capture'){await post('/v1/enterprise/analytics/snapshots',{operation_key:crypto.randomUUID()});await ctx.refreshCurrent();return;}
  if(key==='batch-analytics-tick'){await post('/v1/enterprise/analytics/tick');await ctx.refreshCurrent();return;}
  if(key==='batch-integration-publish'){await post('/v1/platform/publish');await ctx.refreshCurrent();return;}
  const nodes=(resource(state.data,'graph')?.nodes || []).map(n=>({id:n.entity_id,name:n.payload.label}));
  let fields=[],onSubmit;
  if(key==='batch-graph-source') {
    fields=[select('kind','Source type',['employee','department','project','workflow']),text('id','Source record ID'),text('rationale','Source import purpose','textarea')];
    onSubmit=async v=>{const source=await api.request('/v1/enterprise/graph/sources/'+v.kind+'/'+uuid(v.id));return submit('graph','node',source,v.rationale);};
  } else if(key==='batch-graph-node') {
    fields=[text('label','Entity name'),select('kind','Entity type',['person','employee','department','project','workflow','policy','architecture','research','asset','customer','product','incident','skill','model','tool','document','memory','audit','decision','fact']),text('statement','Evidence statement','textarea'),text('source_ref','Source reference'),text('confidence','Evidence confidence0–1','number',{min:0,max:1,value:0.5}),select('classification','Visibility',['tenant','restricted']),text('memory_ids','Company memory IDs (comma separated)','text',{required:false}),text('rationale','Reason for change','textarea')];
    onSubmit=v=>submit('graph','node',{id:crypto.randomUUID(),kind:v.kind,label:v.label,statement:v.statement,owner_id:state.me.id,classification:v.classification,readers:[],source_ref:v.source_ref,source_at:new Date().toISOString(),confidence:Number(v.confidence),effective_at:new Date().toISOString(),expires_at:new Date(Date.now()+90*86400000).toISOString(),memory_ids:v.memory_ids?v.memory_ids.split(',').map(x=>uuid(x.trim())):[],legal_hold:false},v.rationale);
  } else if(key==='batch-graph-edge') {
    mustHave(nodes,'Apply two reviewed graph entities first.');
    fields=[text('from_id','From entity','select',{options:choices(nodes)}),text('to_id','To entity','select',{options:choices(nodes)}),select('relation','Relationship',['owns','manages','member_of','depends_on','governed_by','produced_by','approved_by','references','affects','requires_skill','has_skill','uses_tool','uses_model','caused_by','mitigated_by','learned_from','version_of','simulates','supports','contradicts']),select('inferred','Evidence state',['inferred','verified']),text('source_ref','Relationship evidence'),text('confidence','Confidence0–1','number',{min:0,max:1,value:0.5}),text('rationale','Reason','textarea')];
    onSubmit=v=>submit('graph','edge',{id:crypto.randomUUID(),from_id:uuid(v.from_id),to_id:uuid(v.to_id),relation:v.relation,inferred:v.inferred==='inferred',source_ref:v.source_ref,confidence:Number(v.confidence),expires_at:new Date(Date.now()+90*86400000).toISOString()},v.rationale);
  } else if(['batch-graph-delete','batch-graph-merge'].includes(key)) {
    mustHave(nodes,'Apply graph entities first.');fields=[text('id','Entity','select',{options:choices(nodes)}),text('reason','Reason','textarea')];
    if(key.endsWith('merge'))fields.push(text('target_id','Keep this duplicate','select',{options:choices(nodes)}));
    onSubmit=v=>submit('graph',key.endsWith('merge')?'merge':'delete',v,v.reason);
  } else if(key==='batch-graph-query') {
    fields=[text('root_id','Start entity (optional UUID)','text',{required:false}),select('direction','Direction',['both','out','in']),text('depth','Maximum hops','number',{min:0,max:6,value:2})];
    onSubmit=async v=>{const query=new URLSearchParams({direction:v.direction,depth:v.depth});if(v.root_id)query.set('root_id',uuid(v.root_id));state.batchResult=await api.request('/v1/enterprise/graph?'+query);setTimeout(()=>display('Authorized graph paths',state.batchResult),0);return 'Graph paths loaded.';};
  } else if(key.startsWith('batch-behavior-')) {
    const {people}=await departmentsAndPeople(ctx);const ai=people.filter(x=>x.kind==='ai');
    const dims=['trust','reliability','leadership','collaboration','communication','decision_bias','learning_velocity','creativity','risk_behavior','mentoring','conflict_resolution','adaptability','promotion_readiness'];
    if(key.endsWith('definition')) {
      fields=[select('dimension','Working behavior',dims),text('name','Measure name'),text('rubric','Scoring rubric and examples','textarea'),text('limitations','Known limitations','textarea')];
      onSubmit=v=>submit('behavior','definition',{...v,id:crypto.randomUUID(),minimum_samples:5,version:1},v.rubric);
    } else {
      mustHave(ai,'Create an AI employee first.');fields=[text('employee_id','AI employee','select',{options:choices(ai)})];
      if(key.endsWith('profile'))onSubmit=async v=>{const result=await api.request('/v1/enterprise/behavior/'+uuid(v.employee_id));setTimeout(()=>display('Evidence and uncertainty',result),0);return 'Profile loaded.';};
      else if(key.endsWith('appeal')){fields.push(text('reason','What should be reconsidered?','textarea'));onSubmit=v=>post('/v1/enterprise/behavior/'+uuid(v.employee_id)+'/appeals',{reason:v.reason});}
      else if(key.endsWith('observation')) {
        fields.push(text('definition_id','Reviewed metric definition ID'),text('task_id','Completed task with QA'),select('dimension','Dimension',dims),text('scope','Work domain'),select('complexity','Task complexity',['routine','complex','novel']),select('risk','Risk',['low','medium','high']),text('score','Rubric score0–1','number',{min:0,max:1}),text('rationale','Source-backed rationale','textarea'));
        onSubmit=v=>submit('behavior','observation',{...v,id:crypto.randomUUID(),score:Number(v.score),expires_at:new Date(Date.now()+60*86400000).toISOString()},v.rationale);
      } else if(key.endsWith('decision')) {
        fields.push(text('scope','Target work domain'),select('action','Readiness review',['assignment','promotion','autonomy','learning','hiring_gap']),text('rationale','Evidence and independent judgment','textarea'));
        onSubmit=v=>submit('behavior','decision',{...v,id:crypto.randomUUID(),expires_at:new Date(Date.now()+30*86400000).toISOString()},v.rationale);
      } else {fields.push(text('appeal_id','Appeal ID'),select('resolution','Outcome',['upheld','corrected']),text('excluded','Observation IDs to exclude (comma separated)','text',{required:false}),text('rationale','Resolution rationale','textarea'));onSubmit=v=>submit('behavior','resolve_appeal',{id:crypto.randomUUID(),employee_id:v.employee_id,appeal_id:v.appeal_id,resolution:v.resolution,excluded_observation_ids:v.excluded?v.excluded.split(',').map(x=>uuid(x.trim())):[],rationale:v.rationale},v.rationale);}
    }
  } else if(key==='batch-analytics-dashboard') {
    fields=[select('dashboard','Dashboard',['executive','department','employee','finance','workflow','qa','security','architecture','infrastructure','knowledge','memory','innovation','digital_twin','meta_brain','health']),text('department_id','Department ID when scoped','text',{required:false}),text('employee_id','Employee ID when scoped','text',{required:false})];
    onSubmit=async v=>{const query=new URLSearchParams(Object.fromEntries(Object.entries(v).filter(([,x])=>x)));const result=await api.request('/v1/enterprise/analytics/dashboard?'+query);setTimeout(()=>display('Observed metrics and lineage',result),0);return 'Dashboard loaded.';};
  } else if(key==='batch-analytics-forecast') {
    fields=[select('metric','Metric',['backlog','qa_pass_rate','task_failure_rate','tasks','security_events','memory_records']),text('horizon','Days ahead','number',{min:1,max:90,value:7})];onSubmit=async v=>{const result=await api.request('/v1/enterprise/analytics/history/'+v.metric+'?horizon_days='+v.horizon);setTimeout(()=>display('Forecast, evidence and anomaly',result),0);return 'Analysis loaded.';};
  } else if(key==='batch-analytics-schedule') {
    fields=[select('report','Report',['executive','finance','workflow','qa','security','architecture','infrastructure','knowledge','memory','innovation','digital_twin','meta_brain','health']),select('cadence','Reporting cycle',['weekly','monthly','quarterly','annual']),text('rationale','Reporting purpose','textarea')];onSubmit=v=>submit('analytics','schedule',{id:crypto.randomUUID(),report:v.report,cadence:v.cadence,enabled:true},v.rationale);
  } else if(key==='batch-github-project') {
    fields=[text('goal_id','Approved project goal ID'),text('repository','Private repository name'),text('pm_id','Project manager employee ID'),text('developers','Developer IDs, comma separated'),text('qa_id','Independent QA employee ID'),text('roadmap_ref','Approved roadmap reference'),text('rationale','CEO project approval rationale','textarea')];
    onSubmit=v=>submit('integration','github_project',{id:crypto.randomUUID(),goal_id:uuid(v.goal_id),repository:v.repository,pm_id:uuid(v.pm_id),developer_ids:v.developers.split(',').map(x=>uuid(x.trim())),qa_id:uuid(v.qa_id),roadmap_ref:v.roadmap_ref,enabled:true},v.rationale);
  } else if(key==='batch-github-operation') {
    fields=[text('project_id','Approved GitHub project ID'),select('operation','Operation',['create_repository','link_repository','initialize_develop','create_issue','update_issue','commit_files','create_pull_request']),text('payload','Exact change payload (JSON)','textarea',{value:'{}'}),text('rationale','Change and QA rationale','textarea')];
    onSubmit=v=>submit('integration','github_operation',{id:crypto.randomUUID(),project_id:uuid(v.project_id),operation:v.operation,payload:JSON.parse(v.payload)},v.rationale);
  } else if(key==='batch-github-execute' || key==='batch-github-status') {
    fields=[text('id',key.endsWith('execute')?'Approved operation ID':'GitHub project ID','text',{value:id || ''})];
    onSubmit=async v=>{const result=key.endsWith('execute')?await post('/v1/platform/github/operations/'+uuid(v.id)+'/execute'):await api.request('/v1/platform/github/projects/'+uuid(v.id)+'/status');setTimeout(()=>display('GitHub project result',result),0);return 'GitHub operation inspected.';};
  } else if(key==='batch-integration-client') {
    fields=[text('name','Integration name'),select('type','Client type',['confidential','public']),text('subject_id','Authorized principal ID'),text('department_id','Department restriction (optional)','text',{required:false}),text('scopes','Allowed scopes, comma separated','text',{value:'tasks:read,events:read'}),text('redirects','Exact redirect URIs, one per line','textarea',{required:false}),text('rationale','Purpose and security review','textarea')];
    onSubmit=v=>submit('integration','client',{id:crypto.randomUUID(),name:v.name,type:v.type,subject_id:uuid(v.subject_id),department_id:v.department_id?uuid(v.department_id):null,scopes:v.scopes.split(',').map(x=>x.trim()),redirect_uris:v.redirects?v.redirects.split('\n').map(x=>x.trim()).filter(Boolean):[],enabled:true,requests_per_minute:60},v.rationale);
  } else if(key==='batch-integration-webhook') {
    fields=[text('client_id','Reviewed client ID'),text('url','HTTPS notification endpoint'),text('rationale','Event sharing purpose','textarea')];onSubmit=v=>submit('integration','webhook',{id:crypto.randomUUID(),client_id:uuid(v.client_id),url:v.url,event_types:['task.changed.v1'],enabled:true},v.rationale);
  } else if(key==='batch-integration-key' || key==='batch-integration-rotate') {
    fields=[text('id',key.endsWith('key')?'Confidential client ID':'Webhook subscription ID')];if(key.endsWith('key'))fields.push(select('kind','Credential type',['api_key','client_secret']));
    onSubmit=async v=>{const result=key.endsWith('key')?await post('/v1/platform/clients/'+uuid(v.id)+'/credentials',{kind:v.kind}):await post('/v1/platform/webhooks/'+uuid(v.id)+'/rotate');setTimeout(()=>display('Copy credential now; shown once',result),0);return 'Credential issued.';};
  } else if(key==='batch-integration-plugin') {
    fields=[text('id','Plugin ID (blank for new)','text',{required:false}),text('client_id','Reviewed client ID'),text('name','Plugin name'),text('version','Version','text',{value:'1.0.0'}),select('extension','Extension',['connector','dashboard','workflow','tool','memory','evaluation','reporting']),select('state','Lifecycle state',['installed','configured','enabled','disabled','deprecated','removed']),text('manifest_sha256','Reviewed manifest SHA256'),text('permissions','Scopes, comma separated','text',{value:'tasks:read'}),text('rationale','Review and configuration rationale','textarea')];onSubmit=v=>submit('integration','plugin',{id:v.id?uuid(v.id):crypto.randomUUID(),client_id:uuid(v.client_id),name:v.name,version:v.version,extension:v.extension,state:v.state,manifest_sha256:v.manifest_sha256,permissions:v.permissions.split(',').map(x=>x.trim()),configuration:{}},v.rationale);
  } else throw new Error('Unknown enterprise action.');
  openDialog(ctx,{title:'Enterprise '+key.split('-').slice(1).join(' '),description:'Changes are bound to exact evidence and require independent review before application.',fields,button:'Continue',onSubmit});
}
