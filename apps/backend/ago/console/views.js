/** M9 views. Every dynamic backend/user string is HTML-escaped. */
import {
  safe, num, amount, dateText, shortId, statusTone, percent,
  resource, errorMessage, formatRisk, fitnessDelta, validateProfile,
} from "./core.js";

export const PAGES = Object.freeze({
  overview: { title: "Overview", heading: "Your organization at a glance", eyebrow: "COMMAND OVERVIEW",
    description: "A live operating picture, grounded in your organization's records—not synthetic KPIs." },
  strategy: { title: "Strategy", heading: "Strategy & execution", eyebrow: "COMPANY BRAIN",
    description: "From goals to plans, and from approved plans to governed tasks." },
  governance: { title: "Governance", heading: "Governance & oversight", eyebrow: "HUMAN IN CONTROL",
    description: "Independent decisions, protected task lifecycles and executive council motions." },
  organization: { title: "Organization", heading: "People & departments", eyebrow: "ORGANIZATIONAL STRUCTURE",
    description: "A single view of your departments, human operators and AI employees." },
  knowledge: { title: "Knowledge", heading: "Institutional knowledge", eyebrow: "EVIDENCE & MEMORY",
    description: "Trustworthy provenance starts with independent human verification." },
  tools: { title: "Operations & Tools", heading: "Enterprise operations", eyebrow: "CONTROLLED EXECUTION",
    description: "Registered tools, authorized automation and immutable execution records." },
  calendar: { title: "Calendar", heading: "Organizational calendar", eyebrow: "SHARED COORDINATION",
    description: "Time-bound commitments and visibility-controlled internal events." },
  twin: { title: "Digital Twin", heading: "Organization Digital Twin", eyebrow: "EXECUTIVE INTELLIGENCE LAB",
    description: "Compare alternative operating thresholds with recorded evidence. Simulations do not apply changes." },
});
const icon = (name) => '<svg class="ico" aria-hidden="true"><use href="#i-' + name + '"></use></svg>';
const maybe = (value) => value === null || value === undefined || value === "" ? "—" : safe(value);
const badge = (status) => '<span class="status-badge ' + statusTone(status) + '">' + maybe(String(status ?? "unknown").replaceAll("_", " ")) + "</span>";
const empty = (title, detail = "There are no records yet.") =>
  '<div class="empty-state">' + icon("layers") + '<strong>' + safe(title) + "</strong>" + safe(detail) + "</div>";
const panel = (title, body, subtitle = "") => '<section class="panel"><div class="panel-head"><h3>' +
  safe(title) + '</h3><small>' + safe(subtitle) + '</small></div>' + body + "</section>";
const section = (title, info = "") => '<div class="section-title"><h2>' + safe(title) +
  '</h2><small>' + safe(info) + "</small></div>";
const action = (label, key, id = "", style = "soft") => '<button type="button" class="btn btn-tiny btn-' + style +
  '" data-action="' + safe(key) + '"' + (id ? ' data-id="' + safe(id) + '"' : "") + ">" + safe(label) + "</button>";
const meter = (value) => '<div class="progress-track"><div class="progress-fill" style="width:' + percent(value) + '%"></div></div>';
const risks = (flags) => !Array.isArray(flags) || !flags.length
  ? '<span class="risk-pill clean">No flagged conditions</span>'
  : flags.map(x => '<span class="risk-pill">' + safe(formatRisk(x)) + "</span>").join("");
function unavailable(data, key, zero) {
  const message = errorMessage(data, key);
  return message
    ? '<div class="empty-state">' + icon("lock") + "<strong>" +
      safe(message) + "</strong>" + safe(key) + " is available only with the relevant grant.</div>"
    : zero;
}
function list(data, key) { const item = resource(data, key); return Array.isArray(item) ? item : []; }
function capability(state, name) {
  return Array.isArray(state.me?.permissions) && state.me.permissions.includes(name);
}
function table(headers, rows, fallback = empty("Nothing here yet")) {
  return rows.length ? '<div class="table-scroll" tabindex="0" role="region" aria-label="Scrollable records"><table class="data-table"><thead><tr>' +
    headers.map(x => '<th scope="col">' + safe(x) + "</th>").join("") +
    "</tr></thead><tbody>" + rows.join("") + "</tbody></table></div>" : fallback;
}
function metric(label, value, note, glyph, highlight = false) {
  return '<div class="metric' + (highlight ? " highlight" : "") + '"><div class="metric-label">' +
    icon(glyph) + safe(label) + '</div><div class="metric-value">' +
    safe(value) + '</div><div class="metric-foot">' + safe(note) + "</div></div>";
}
function layout(page, actionButtons, body) {
  const p = PAGES[page];
  return '<div class="page-head"><div><span class="page-eyebrow">' + p.eyebrow + "</span><h1>" +
    safe(p.heading) + '</h1><p>' + safe(p.description) + '</p></div><div class="page-actions">' +
    actionButtons + "</div></div>" + body;
}
function statusRows(tasks) {
  const values = ["proposed","waiting_approval","running","completed","failed"];
  const count = tasks.reduce((acc, x) => { acc[String(x.status)] = (acc[String(x.status)] || 0) + 1; return acc; }, {});
  const total = tasks.length;
  return values.map(name => '<div class="keyval"><span>' + safe(name.replaceAll("_"," ")) +
    '</span><strong>' + num(count[name] || 0) + "</strong></div>" +
    meter(total ? (count[name] || 0) / total * 100 : 0)).join("");
}
export function renderOverview(data, state) {
  const score = resource(data, "score");
  const tasks = list(data, "tasks");
  const approvals = list(data, "approvals");
  const brief = resource(data, "brief");
  const count = score?.counts || {};
  const pending = resource(data, "approvals") === null ? "—"
    : num(approvals.filter(x => x.status === "pending").length);
  const money = score?.virtual_credit_budget;
  const metrics = '<div class="metric-grid">' +
    metric("Governed tasks", score ? num(count.tasks || 0) : "—", "Organization-wide", "activity", true) +
    metric("Pending decisions", pending, "Human review required", "shield") +
    metric("AI workforce runs", score ? num(count.agent_runs || 0) : "—", "Recorded execution", "bolt") +
    metric("Available virtual credits", money ? amount(money.remaining) : "—",
      "Internal credits, not currency", "chart") + "</div>";
  const taskRows = tasks.slice(0, 5).map(x =>
    '<div class="list-row"><span class="row-icon">' + icon("layers") +
    '</span><div class="row-main"><strong>' + maybe(x.action) +
    '</strong><small>Task ' + safe(shortId(x.id)) + '</small></div>' +
    badge(x.status) + "</div>").join("");
  const approvalRows = approvals.filter(x => x.status === "pending").slice(0, 4)
    .map(x => '<div class="list-row"><span class="row-icon">' + icon("shield") +
    '</span><div class="row-main"><strong>' + maybe(x.action) +
    '</strong><small>Requested ' + safe(dateText(x.created_at)) + '</small></div>' +
    (capability(state, "approval:decide") && x.requester_id !== state.me?.id ? action("Review","review-approval",x.id) : badge("pending")) + "</div>").join("");
  const intelligence = brief?.snapshot;
  const risksHTML = intelligence ? risks(intelligence.risk_flags) : risks(["insufficient_data"]);
  const intelligenceBody = '<div class="panel-body">' +
    '<div class="mini-stat"><div><small>Evidence-backed fitness</small><strong>' +
    (intelligence?.fitness == null ? "N/A" : safe(intelligence.fitness)) +
    '</strong></div><div><small>Latest evidence</small><strong>' +
    (intelligence ? safe(shortId(intelligence.id)) : "None") +
    '</strong></div></div><div class="section-title"><h2>Risk signals</h2></div>' +
    '<div class="pill-list">' + risksHTML + '</div><p class="muted" style="font-size:11px;line-height:1.8;margin:17px 0 0">' +
    (intelligence ? "The displayed assessment is from a recorded snapshot, not a live prediction."
      : "No executive snapshot captured. Use Digital Twin to capture evidence when authorized.") +
    '</p></div>';
  const taskBody = unavailable(data, "tasks", taskRows || empty("No tasks created", "Propose goals and approved plans to begin."));
  const approvalsBody = unavailable(data, "approvals", approvalRows || empty("Nothing awaiting review"));
  const twinBody = unavailable(data, "brief", intelligenceBody);
  return layout("overview", action("Open Digital Twin","go-twin","","soft") +
    action("Refresh data","refresh","","primary"), metrics +
    section("Operational pulse", "Live tenant data") +
    '<div class="two-col"><div class="col">' +
    panel("Recent governed tasks", taskBody, score ? num(count.tasks || 0) + " total" : "") +
    panel("Human approval queue", approvalsBody, pending + " pending") +
    '</div><div class="col">' +
    panel("Executive intelligence", twinBody, "M7 snapshot") +
    panel("Task lifecycle", '<div class="panel-body">' +
      (resource(data,"tasks") === null ? unavailable(data,"tasks","") : statusRows(tasks)) +
      '</div>', "Current records") + '</div></div>');
}
export function renderStrategy(data, state) {
  const goals = list(data, "goals"), plans = list(data, "plans");
  const decisions = list(data, "approvals");
  const decisionFor = plan => decisions.find(x => x.id === plan.approval_id);

  const goalsRows = goals.map(x => '<tr><td class="primary">' + maybe(x.title) +
    '</td><td>' + badge(x.status) + '</td><td><span class="text-mono">' +
    safe(shortId(x.id)) + '</span></td><td>' +
    (x.parent_id ? '<span class="text-mono">' + safe(shortId(x.parent_id)) + '</span>' : "—") +
    "</td></tr>");
  const plansRows = plans.map(x => '<tr><td class="primary">' + maybe(x.title) +
    '</td><td>' + badge(x.status) + '</td><td><span class="text-mono">' +
    safe(shortId(x.goal_id)) + '</span></td><td><div class="inline-actions">' +
    action("Steps","plan-steps",x.id) +
    (x.status === "draft" ? action("Add step","plan-add-step",x.id) +
      action("Submit","plan-submit",x.id,"primary") : "") +
    (x.status === "pending_approval"
      ? (decisionFor(x)?.status === "approved"
        ? action("Activate","plan-activate",x.id,"primary")
        : (decisionFor(x)?.status === "rejected" ? badge("rejected")
          : badge("pending")))
      : "") +
    (x.status === "active" ? action("Create tasks","plan-materialize",x.id,"primary") : "") +
    '</div></td></tr>');
  return layout("strategy",
    (capability(state,"brain:manage") ? action("New goal","new-goal","","primary") +
      action("New plan","new-plan") : ""),
    '<div class="info-strip">' + icon("shield") +
    '<span>A plan requires its own independent approval before activation. Every resulting task still requires its own approval.</span></div>' +
    section("Strategic objectives", num(goals.length) + " recorded") +
    panel("Goals", unavailable(data,"goals",table(
      ["Goal","Status","ID","Parent"],goalsRows,empty("No goals yet","Create your first organizational objective."),
    ))) + section("Execution plans",num(plans.length) + " plans") +
    panel("Governed plans",unavailable(data,"plans",table(
      ["Plan","State","Goal","Actions"],plansRows,empty("No plans yet","Attach a new plan to an active goal."),
    ))));
}
export function renderGovernance(data, state) {
  const approvals = list(data,"approvals"), tasks = list(data,"tasks");
  const motions = list(data,"motions"), reviews = list(data,"reviews");
  const qaqueue = list(data,"qaqueue");
  const approvedIds = new Set(approvals.filter(x=>x.status==="approved").map(x=>x.id));
  const aRows = approvals.map(x => '<tr><td class="primary">' + maybe(x.action) +
    '<div class="text-mono">' + safe(shortId(x.id)) + '</div></td><td>' +
    badge(x.status) + '</td><td>' + safe(dateText(x.created_at)) +
    '</td><td>' + (x.status==="pending" &&
      x.requester_id !== state.me?.id && capability(state,"approval:decide")
      ? '<div class="inline-actions">' + action("Approve","approve",x.id,"primary") +
        action("Reject","reject",x.id,"danger") + "</div>"
      : '<span class="muted">—</span>') + '</td></tr>');
  const nextAction = x => {
    if (x.status==="proposed" &&
        capability(state,"task:create") && capability(state,"approval:request")) {
      return action("Request approval","task-request-approval",x.id,"primary");
    }
    if (x.status==="waiting_approval" && approvedIds.has(x.approval_id)) {
      if (String(x.action).startsWith("tool:") && capability(state,"tool:dispatch"))
        return action("Run approved tool","tool-run",x.id,"primary");
      if (["internal:brief","research:brief"].includes(String(x.action)) &&
        capability(state,"agent:dispatch"))
        return action("Run approved AI","agent-run",x.id,"primary");
    }
    return '<span class="muted">—</span>';
  };
  const tRows = tasks.map(x => '<tr><td class="primary">' + maybe(x.action) +
    '</td><td>' + badge(x.status) + '</td><td><span class="text-mono">' +
    safe(shortId(x.assignee_id)) + '</span></td><td>' +
    (x.approval_id ? '<span class="text-mono">' + safe(shortId(x.approval_id)) +
    '</span>' : "—") + '</td><td>' + nextAction(x) + '</td></tr>');
  const pendingQaRows = qaqueue.map(x => '<tr><td class="primary">' +
    maybe(x.action) + '</td><td>' + badge(x.status) +
    '</td><td><span class="text-mono">' + safe(shortId(x.id)) +
    '</span></td><td>' + (capability(state,"qa:review")
      ? action("Review outcome","qa-review",x.id,"primary")
      : '<span class="muted">Read only</span>') + '</td></tr>');
  const qaRows = reviews.map(x=>'<tr><td class="primary"><span class="text-mono">' +
    safe(shortId(x.task_id)) + '</span></td><td>' + badge(x.verdict) +
    '</td><td><span class="text-mono">' + safe(shortId(x.reviewer_id)) +
    '</span></td><td>' + safe(dateText(x.created_at)) + '</td></tr>');
  const councilRows = motions.map(x => '<tr><td class="primary">' + maybe(x.title) +
    '<div class="muted">' + maybe(x.rationale) + '</div></td><td>' + badge(x.status) +
    '</td><td>' + num(Number(x.yes_votes)||0) + "/" + num(x.required_votes) +
    ' yes</td><td><div class="inline-actions">' +
    (x.status==="open" ? (x.proposer_id !== state.me?.id &&
      capability(state,"council:vote") ? action("Vote","council-vote",x.id) : "") +
      (capability(state,"council:finalize") ?
        action("Finalize","council-finalize",x.id,"primary") : "") : "") +
    "</div></td></tr>");
  return layout("governance",capability(state,"council:propose") ?
    action("Propose motion","new-motion","","primary") : "",
    '<div class="info-strip">' + icon("shield") +
    "<span>Approvals remain independent. You cannot approve your own requests. Council motions are advisory only.</span></div>" +
    section("Independent review","Human decisions") +
    panel("Approvals",unavailable(data,"approvals",table(
      ["Request","Status","Created","Decision"],aRows,empty("Review queue is clear"),
    ))) + section("Task control","Governed execution") +
    panel("Task register",unavailable(data,"tasks",table(
      ["Action","State","Assignee","Approval","Next step"],tRows,
      empty("No governed tasks"),
    ))) + section("Independent quality assurance",num(qaqueue.length)+" awaiting review") +
    panel("Pending QA",unavailable(data,"qaqueue",table(
      ["Completed task","State","Task ID","Action"],pendingQaRows,
      empty("No completed tasks awaiting independent QA"),
    ))) +
    panel("QA outcomes",unavailable(data,"reviews",table(
      ["Task","Verdict","Reviewer","Recorded"],qaRows,empty("No QA verdicts yet"),
    ))) + section("Executive council","Human quorum") +
    panel("Council motions",unavailable(data,"motions",table(
      ["Motion","Status","Votes","Action"],councilRows,empty("No motions recorded"),
    ))));
}
export function renderOrganization(data, state) {
  const depts = list(data,"departments"), people = resource(data,"employees");
  const rows = depts.map(x => {
    const team = (people && Array.isArray(people[x.id])) ? people[x.id] : [];
    return '<div class="list-row"><span class="row-icon">' + icon("network") +
      '</span><div class="row-main"><strong>' + maybe(x.name) +
      '</strong><small>' + num(team.length) + ' team members · ' +
      safe(shortId(x.id)) + '</small></div><span class="chip">' +
      num(team.filter(y => y.kind==="ai").length) + ' AI</span></div>';
  });
  const allPeople = people && typeof people === "object" ? Object.values(people).flat() : [];
  const peopleRows = allPeople.map(x => '<div class="person-card panel"><span class="avatar">' +
    safe(String(x.name||"A").slice(0,2).toUpperCase()) +
    '</span><div><strong>' + maybe(x.name) +
    '</strong><small>Department ' + safe(shortId(x.department_id)) +
    '</small></div>' + badge(x.kind) + '</div>').join("");
  return layout("organization",
    capability(state,"organization:manage") ?
      action("Add department","new-department") + action("Add AI employee","new-ai","","primary") : "",
    '<div class="metric-grid">' +
    metric("Departments",resource(data,"departments") ? num(depts.length) : "—",
      "Tenant-defined structure","network",true) +
    metric("Total personnel",people ? num(allPeople.length) : "—",
      "Human + AI employee records","layers") +
    metric("AI employees",people ? num(allPeople.filter(x=>x.kind==="ai").length) : "—",
      "Registered virtual workers","brain") +
    metric("Human personnel",people ? num(allPeople.filter(x=>x.kind==="human").length) : "—",
      "Human organizational roles","shield") +
    '</div>' + section("Department structure") +
    panel("Departments",unavailable(data,"departments",rows.join("") ||
      empty("No departments found"))) +
    section("Personnel directory") +
    (people ? '<div class="pair-grid">' + (peopleRows ||
      '<div class="panel">' + empty("No employees found") + "</div>") + "</div>"
      : unavailable(data,"employees",empty("No personnel available"))));
}
export function renderKnowledge(data, state) {
  const verified = list(data,"verified"), pending = list(data,"pending");
  const verifiedRows = verified.map(x =>
    '<div class="list-row"><span class="row-icon">' + icon("book") +
    '</span><div class="row-main"><strong>' + maybe(x.label) +
    '</strong><small>' + maybe(x.statement) +
    '</small><small>Source: ' + maybe(x.source_ref) + '</small></div>' +
    badge("verified") + "</div>").join("");
  const pendingRows = pending.map(x =>
    '<div class="list-row"><span class="row-icon">' + icon("alert") +
    '</span><div class="row-main"><strong>' + maybe(x.label) +
    '</strong><small>' + maybe(x.statement) +
    '</small><small>Source: ' + maybe(x.source_ref) + '</small></div>' +
    (capability(state,"knowledge:review") && x.author_id !== state.me?.id ?
      action("Review","knowledge-review",x.id) : badge("pending")) + "</div>").join("");
  return layout("knowledge", capability(state,"knowledge:write") ?
    action("Propose evidence","new-knowledge","","primary") : "",
    '<div class="info-strip">' + icon("shield") +
    "<span>Verified means an independent human inspected a source. It is not a universal guarantee of factual correctness.</span></div>" +
    section("Verified knowledge",num(verified.length)+" entries") +
    panel("Evidence library",unavailable(data,"verified",verifiedRows ||
      empty("No verified knowledge","Propose source-backed evidence for review."))) +
    section("Pending review",num(pending.length)+" proposals") +
    panel("Review queue",unavailable(data,"pending",pendingRows ||
      empty("No pending evidence"))));
}
export 
function renderEnterpriseSummary(data, state = {}) {
  const manage = capability(state,"organization:manage");
  const approvals = list(data,"approvals");
  const evidence = list(data,"enterpriseEvidence");
  const revisions = list(data,"enterpriseRevisions");
  const approval = id => approvals.find(x=>x.id===id);
  const intentRowsSaved = evidence.filter(x=>x.kind==="intent").slice(0,20).map(x=>
    '<tr><td>'+maybe(x.payload.operation)+'</td><td>'+badge(approval(x.payload.approval_id)?.status || "unknown")+
    '</td><td>'+action("Review parameters","enterprise-evidence",x.id)+
    (manage && approval(x.payload.approval_id)?.status==="approved" && x.payload.requester_id===state.me?.id
      ?action("Apply exact request","enterprise-apply-intent",x.id):"")+ '</td></tr>');
  const evidenceRows = evidence.filter(x=>!['intent','intent_result'].includes(x.kind)).slice(0,20).map(x=>
    '<tr><td>'+maybe(x.kind)+'</td><td>'+safe(dateText(x.created_at))+'</td><td>'+badge(x.reviewed_at?"reviewed":"unreviewed")+
    '</td><td>'+action("Inspect evidence","enterprise-evidence",x.id)+(manage && !x.reviewed_at?
      action("Independent review","enterprise-review-evidence",x.id):"")+ '</td></tr>');
  const revisionRows = revisions.slice(0,20).map(x=>'<tr><td>'+maybe(x.title)+'</td><td>'+maybe(x.base_revision)+
    '</td><td>'+badge(x.applied_revision?"applied":x.status)+'</td><td>'+
    (manage && x.status==="approved" && !x.applied_revision && x.actor_id===state.me?.id?
      action("Apply revision","enterprise-apply-revision",x.id):"")+ '</td></tr>');
  const currentMode = resource(data,"enterpriseModes")?.effective;
  const capacity = resource(data,"enterpriseCapacity");
  const capacityPolicies = Array.isArray(capacity?.policies) ? capacity.policies : [];
  const queue = list(data,"enterpriseWorkQueue");
  const orgIntents = list(data,"enterpriseOrgIntents");
  const strategicPlans = list(data,"enterprisePlans");
  const costs = list(data,"enterpriseCosts");
  const budgets = list(data,"enterpriseBudgets");
  const assets = list(data,"enterpriseAssets");
  const consumption = list(data,"enterpriseAssetUsage");
  const scenarios = list(data,"enterpriseTwin");
  const requests = list(data,"enterpriseAssistance");
  const hr = resource(data,"enterpriseOrgHistory");
  const orgEvents = Array.isArray(hr?.personnel) ? hr.personnel : [];
  const decisions = list(data,"enterpriseEvolutionReviews");
  const observed = list(data,"enterpriseTwinComparisons");
  const moneyRows = costs.slice(0,10).map(x=>'<tr><td class="primary">'+maybe(x.category)+
    '</td><td>'+maybe(x.provider)+'</td><td>'+maybe(x.observed_amount)+
    ' '+maybe(x.currency)+'</td><td>'+badge(x.evidence_state)+'</td></tr>');
  const planRows = strategicPlans.slice(0,10).map(x=>'<tr><td class="primary">'+maybe(x.title)+
    '</td><td>'+maybe(x.horizon)+'</td><td>'+safe(dateText(x.ends_at))+
    '</td><td>'+maybe(x.budget_ceiling)+'</td></tr>');
  const assetRows = assets.slice(0,10).map(x=>'<tr><td class="primary">'+maybe(x.name)+
    '</td><td>'+maybe(x.asset_kind)+'</td><td>'+maybe(x.version)+
    '</td><td>'+badge(x.status)+'</td><td>'+action("Impact","enterprise-asset-impact",x.id)+action("Content","enterprise-asset-view",x.id)+(manage && ["draft","proposed"].includes(x.status)?action("Publish / request review","enterprise-publish",x.id):"")+'</td></tr>');
  const budgetRows = budgets.slice(0,10).map(x=>'<tr><td>'+maybe(x.scope_kind)+
    '</td><td>'+maybe(x.approved_ceiling)+' '+maybe(x.currency)+
    '</td><td>'+safe(shortId(x.approval_id))+'</td></tr>');
  const usageRows = consumption.slice(0,10).map(x=>'<tr><td>'+safe(shortId(x.asset_id))+
    '</td><td>'+num(Number(x.consumptions))+'</td></tr>');
  const simRows = scenarios.slice(0,10).map(x=>'<tr><td>'+safe(dateText(x.created_at))+
    '</td><td>'+safe(shortId(x.snapshot_id))+'</td><td>'+
    (x.calibrated?'Calibrated':'Uncalibrated')+'</td><td>'+
    maybe(x.data_coverage)+'</td></tr>');
  const helpRows = requests.slice(0,10).map(x=>'<tr><td>'+safe(shortId(x.employee_id))+
    '</td><td>'+maybe(x.reason)+'</td><td>'+badge(x.severity)+
    '</td><td>'+badge(x.outcome || "open")+'</td></tr>');
  const hrRows = orgEvents.slice(0,10).map(x=>'<tr><td>'+safe(shortId(x.employee_id))+
    '</td><td>'+badge(x.change_kind)+'</td><td>'+maybe(x.role_level)+
    '</td><td>'+safe(dateText(x.created_at))+'</td></tr>');
  const evolutionRows = decisions.slice(0,10).map(x=>'<tr><td>'+
    safe(shortId(x.observation_id))+'</td><td>'+badge(x.decision)+
    '</td><td>'+safe(dateText(x.created_at))+'</td></tr>');
  const comparisonRows = observed.slice(0,10).map(x=>'<tr><td>'+
    safe(shortId(x.scenario_id))+'</td><td>'+safe(shortId(x.later_snapshot_id))+
    '</td><td>Descriptive only</td><td>'+safe(dateText(x.created_at))+'</td></tr>');
  const capacityRows = capacityPolicies.slice(0,10).map(x=>
    '<tr><td>'+maybe(x.scope_kind)+'</td><td>'+safe(shortId(x.scope_id || "company"))+
    '</td><td>'+num(Number(x.max_running))+'</td><td>'+maybe(x.rationale)+'</td></tr>');
  const queuedRows = queue.slice(0,12).map(x=>
    '<tr><td>'+safe(shortId(x.task_id))+'</td><td>'+
    num(Number(x.priority))+'</td><td>'+badge(x.task_status)+'</td><td>'+
    badge(x.lease_state || "queued")+'</td></tr>');
  const intentRows = orgIntents.slice(0,10).map(x=>
    '<tr><td>'+maybe(x.change_kind)+'</td><td>'+
    maybe(x.payload?.name || x.payload?.target_id)+'</td><td>'+
    maybe(x.payload?.reason)+'</td><td>'+badge(x.status)+(manage && x.status==="approved"?action("Apply HR change","enterprise-apply-hr",x.id):"")+'</td></tr>');
  return section("Organizational operating system","Sections 21–27 · persisted evidence")+
    (manage?'<div class="page-actions">'+action("Organization workflows","enterprise-command")+
      action("Run one approved offline task","enterprise-claim")+'</div>':"")+
    panel("Saved operation requests",table(["Workflow","Independent approval","Action"],intentRowsSaved,empty("No saved operation requests")))+
    panel("Versioned plan review requests",table(["Plan","Base revision","Status","Action"],revisionRows,empty("No plan revisions awaiting review")))+
    panel("Operational evidence and forecasts",unavailable(data,"enterpriseEvidence",table(["Evidence","Captured","Review","Action"],evidenceRows,empty("Capture an operating cycle, planning rollup or Twin state"))))+
    '<div class="info-strip">'+icon("shield")+
    '<span>Human approvals govern all operational changes. Costs are unverified unless independently reconciled; scenarios never apply changes.</span></div>'+
    '<div class="metric-grid">'+
    metric("Effective operating mode",currentMode?.mode || "Unavailable",
      "Company scope · source "+String(currentMode?.source || "not authorized"),"shield")+
    metric("Planning horizons",resource(data,"enterprisePlans") ? num(strategicPlans.length) : "—",
      "Approved strategy hierarchy records","layers")+
    metric("Internal assets",resource(data,"enterpriseAssets")?num(assets.length):"—",
      "Versioned tenant catalog","layers")+
    metric("Twin scenarios",resource(data,"enterpriseTwin")?num(scenarios.length):"—",
      "Read-only historical simulations","chart")+
    metric("Running tasks",capacity ? num(Number(capacity.total_running)) : "—",
      "Tenant-wide database-governed slots","layers")+'</div>'+
    panel("Governed execution capacity",unavailable(data,"enterpriseCapacity",
      table(["Scope","Target","Max running","Reviewed rationale"],capacityRows,
        empty("Default company / department / employee limits apply"))))+
    panel("Durable approved-work queue",unavailable(data,"enterpriseWorkQueue",
      table(["Task","Priority","Task state","Lease state"],queuedRows,
        empty("No approved task queue entries"))))+
    panel("Immutable organizational approval details",unavailable(data,"enterpriseOrgIntents",
      table(["Change","Employee / department","Exact reviewed reason","Approval"],intentRows,
        empty("No full-payload HR review requests"))))+
    panel("Multi-level plans",unavailable(data,"enterprisePlans",
      table(["Plan","Horizon","Deadline","Budget ceiling"],planRows,empty("No approved planning horizons"))))+
    panel("Observed financial evidence (not verified bills)",unavailable(data,"enterpriseCosts",
      table(["Category","Provider","Amount","Evidence"],moneyRows,empty("No observed costs"))))+
    panel("Governed departmental budgets",unavailable(data,"enterpriseBudgets",
      table(["Scope","Ceiling","Approval"],budgetRows,empty("No financial envelopes"))))+
    panel("Internal marketplace catalog",unavailable(data,"enterpriseAssets",
      table(["Asset","Type","Version","Lifecycle","Actions"],assetRows,empty("No published or draft assets"))))+
    panel("Approved asset consumption",unavailable(data,"enterpriseAssetUsage",
      table(["Asset","Recorded uses"],usageRows,empty("No asset reuse recorded"))))+
    panel("Digital Twin provenance",unavailable(data,"enterpriseTwin",
      table(["Captured","Source snapshot","Calibration","Coverage"],simRows,
        empty("No saved what-if scenarios"))))+
    panel("AI employee safety and assistance",unavailable(data,"enterpriseAssistance",
      table(["Employee","Reason","Severity","Review"],helpRows,
        empty("No recorded assistance requests"))))+
    panel("Reviewed AI employee lifecycle",unavailable(data,"enterpriseOrgHistory",
      table(["Employee","Change","Level","Recorded"],hrRows,
        empty("No independently approved HR changes"))))+
    panel("Governed evolution reviews",unavailable(data,"enterpriseEvolutionReviews",
      table(["Observation","Decision","Recorded"],evolutionRows,
        empty("No reviewed evolution proposals"))))+
    panel("Observed Digital Twin follow-ups",unavailable(data,"enterpriseTwinComparisons",
      table(["Scenario","Actual snapshot","Evidence type","Recorded"],comparisonRows,
        empty("No independently reviewed outcome comparisons"))));
}

function renderTools(data, state) {
  const enrollments = list(data,"enrollments"), runs = list(data,"runs");
  const rules = list(data,"rules"), tasks = list(data,"tasks");
  const approvals = list(data,"approvals");
  const activeCodes = new Set(enrollments.filter(x => x.status==="active").map(x=>x.tool_code));
  const eRows = enrollments.map(x => '<tr><td class="primary">' + maybe(x.tool_code) +
    '</td><td>' + badge(x.status) + '</td><td><span class="text-mono">' +
    safe(shortId(x.id)) + '</span></td><td><div class="inline-actions">' +
    (x.status==="proposed" && capability(state,"tool:enroll") ?
      action("Reconcile","tool-reconcile",x.id) : "") +
    (x.status==="active" && capability(state,"tool:enroll") ?
      action("Disable","tool-disable",x.id,"danger") : "") + "</div></td></tr>");
  const rRows = rules.map(x => '<tr><td class="primary">' + maybe(x.tool_code) +
    '</td><td>' + maybe(x.trigger_kind) + '</td><td>' + badge(x.status) +
    '</td><td>' + (x.status==="active" && capability(state,"automation:manage") ?
      action("Disable","rule-disable",x.id,"danger") : "—") + '</td></tr>');
  const runsRows = runs.map(x => '<tr><td class="primary">' + maybe(x.tool_code) +
    '</td><td>' + badge(x.status) + '</td><td>' + safe(dateText(x.started_at)) +
    '</td><td><span class="text-mono">' + safe(shortId(x.id)) + '</span></td></tr>');
  const approvedIds = new Set(approvals.filter(x => x.status === "approved").map(x => x.id));
  const ready = tasks.filter(x => String(x.action||"").startsWith("tool:") &&
    x.status === "waiting_approval");
  const readyRows = ready.map(x => '<div class="list-row"><span class="row-icon">' +
    icon("bolt") + '</span><div class="row-main"><strong>' +
    maybe(x.action) + '</strong><small>' + safe(shortId(x.id)) +
    " · Requires per-task M2 approval</small></div>" +
    (capability(state,"tool:dispatch") && approvedIds.has(x.approval_id) ?
      action("Run approved task","tool-run",x.id,"primary") : badge("pending")) + '</div>').join("");
  return layout("tools", (capability(state,"tool:enroll") ?
    action("Enroll a tool","new-enrollment") : "") +
    (capability(state,"automation:manage") ? action("New automation","new-rule") : "") +
    (capability(state,"automation:run") ? action("Scan sources","automation-scan","","primary") : ""),
    '<div class="info-strip">' + icon("shield") +
    "<span>Enrolling a tool is not approving execution. Each automated task needs its own independent approval, and completed output needs QA.</span></div>" +
    section("Active capabilities",num(activeCodes.size)+" tools active") +
    panel("Tenant tool enrollments",unavailable(data,"enrollments",table(
      ["Tool","Status","Enrollment","Action"],eRows,
      empty("No tools enrolled","Every tool enrollment requires independent approval."),
    ))) + section("Automated coordination",num(rules.length)+" rules") +
    panel("Department automation rules",unavailable(data,"rules",table(
      ["Tool","Verified source","Status","Action"],rRows,empty("No automation rules"),
    ))) + section("Approved execution","Independent task approval required") +
    panel("Tool task queue",unavailable(data,"tasks",readyRows ||
      empty("No pending tool tasks"))) +
    section("Execution evidence",num(runs.length)+" runs") +
    panel("Enterprise tool runs",unavailable(data,"runs",table(
      ["Tool","State","Started","Run ID"],runsRows,empty("No tool runs recorded"),
    ))) + renderEnterpriseSummary(data,state));
}
export function renderCalendar(data, state) {
  const events = list(data,"events");
  const rows = events.map(x => '<div class="list-row"><span class="row-icon">' + icon("calendar") +
    '</span><div class="row-main"><strong>' + maybe(x.title) +
    '</strong><small>' + safe(dateText(x.starts_at)) + ' — ' +
    safe(dateText(x.ends_at)) + '</small><small>' + maybe(x.detail) + '</small></div>' +
    '<div class="row-action">' + badge(x.status) +
    (x.status==="scheduled" && x.creator_id===state.me?.id &&
      capability(state,"calendar:write") ? action("Cancel","calendar-cancel",x.id,"danger")
      : "") +
    (x.status==="scheduled" && x.invited === true && capability(state,"calendar:respond") ?
      action("RSVP","calendar-rsvp",x.id) : "") + '</div></div>').join("");
  return layout("calendar",capability(state,"calendar:write") ?
    action("Schedule event","new-event","","primary") : "",
    '<div class="info-strip">' + icon("calendar") +
    "<span>Events are records within AGO. No external email invitation or third-party calendar is sent.</span></div>" +
    section("Upcoming window","Next 30 days") +
    panel("Shared commitments",unavailable(data,"events",rows ||
      empty("No upcoming events","Schedule the first organizational event."))));
}
function renderCulture(data,state) {
  const dna=resource(data,"dna"), reflection=resource(data,"reflection");
  const rows=Object.entries(dna?.charter || {}).map(([key,value])=>
    '<div class="keyval"><span>'+safe(key.replaceAll('_',' '))+'</span><strong>'+safe(value)+'</strong></div>').join('');
  const pending=list(data,"dnarecords").filter(x=>x.status==='proposed').map(x=>
    '<div class="list-row"><div class="row-main"><strong>'+safe(x.scope_kind)+' · v'+safe(x.version)+'</strong><small>'+safe(x.rationale)+'</small></div>'+badge(x.status)+
    (capability(state,'meta:dna:activate')?action('Finalize reviewed DNA','reconcile-dna',x.id):'')+'</div>').join('');
  const evals=list(data,'evaluations').map(x=>'<div class="list-row"><div class="row-main"><strong>Observed quality change: '+safe(x.assessment?.observed_delta?.quality_pct ?? 'N/A')+'</strong><small>'+safe(x.change_evidence)+'</small></div>'+badge(x.status)+
    (x.status==='proposed'&&capability(state,'meta:finalize')?action('Finalize reviewed outcome','reconcile-evaluation',x.id):'')+'</div>').join('');
  const recs=list(data,'recommendations').map(x=>'<div class="list-row"><div class="row-main"><strong>'+safe(x.summary)+'</strong></div>'+badge(x.status)+
    (x.status==='proposed'&&capability(state,'meta:finalize')?action('Finalize reviewed recommendation','reconcile-recommendation',x.id):'')+'</div>').join('');
  const actions=(capability(state,'meta:dna:propose')?action('Propose company DNA','propose-company-dna')+action('Propose team or employee DNA','propose-scoped-dna'):'')+
    (capability(state,'meta:dna:read')?action('Inspect employee inheritance','inspect-dna'):'')+
    (capability(state,'meta:recommend')?action('Evaluate observed change','propose-evaluation'):'');
  return section('Company culture and reviewed learning')+panel('Organizational DNA',
    '<div class="panel-body"><p>These are default guidance unless a company version has been approved. Independent approval, permissions and tenant isolation remain mandatory.</p><div class="page-actions">'+actions+'</div>'+unavailable(data,'dna',rows)+pending+'</div>')+
    panel('Historical reflection','<div class="panel-body">'+unavailable(data,'reflection',
      '<p>'+safe(reflection?.sample_count ?? 0)+' verified snapshots. '+safe(reflection?.status || 'No history')+'.</p><p>Observed differences do not prove that a recommendation caused a change.</p>'+
      (reflection?.reflection_findings || []).map(x=>'<p>'+safe(x.concern)+': '+safe(x.proposal)+'</p>').join(''))+'</div>')+
    panel('Recommendations',unavailable(data,'recommendations',recs || empty('No recommendations','Capture evidence and propose a review.')))+
    panel('Observed outcome reviews',unavailable(data,'evaluations',evals || empty('No reviewed comparisons','Record a later snapshot after an endorsed change.')));
}
export function renderTwin(data, state) {
  const active = resource(data,"dna");
  const snapshots = list(data,"snapshots");
  const selected = state.twin?.snapshotId
    ? snapshots.find(x=>x.id===state.twin.snapshotId) || snapshots[0] : snapshots[0];
  const currentProfile = active?.profile || {
    qa_target_pct:85,backlog_limit:5,budget_alert_pct:80,
  };
  const candidate = validateProfile(state.twin?.profile || currentProfile);
  const simulation = state.twin?.simulation;
  const recorded = selected || null;
  const preface = '<div class="twin-banner"><div><span class="eyebrow">' + icon("spark") +
    ' EVIDENCE-BASED EXPLORATION</span><h2>Explore decisions before making them.</h2>' +
    '<p>Run bounded what-if calculations against a recorded organizational snapshot. No policy is saved, no employee is changed and no task is executed.</p></div><span class="twin-visual">' +
    icon("brain") + '</span></div>';
  const selectOptions = snapshots.map(x => '<option value="' + safe(x.id) + '"' +
    (recorded?.id===x.id ? " selected" : "") + '>' +
    safe(dateText(x.created_at)) + ' · ' + safe(shortId(x.id)) + "</option>").join("");
  const rangeDefs = [
    ["qa_target_pct","QA quality target",50,100,1,"%"],
    ["backlog_limit","Backlog alert threshold",0,10000,1," tasks"],
    ["budget_alert_pct","Credit utilization alert",1,100,1,"%"],
  ];
  const ranges = rangeDefs.map(([key,title,min,max,step,suffix]) =>
    '<div class="range-row"><label class="twin-label" for="range-' + key + '">' +
    safe(title) + '<output id="output-' + key + '">' + num(candidate[key]) + safe(suffix) +
    '</output></label><input type="range" data-twin-field="' + key +
    '" id="range-' + key + '" min="' + min + '" max="' + max +
    '" step="' + step + '" value="' + candidate[key] + '"></div>').join("");
  const baselineScore = recorded?.fitness == null ? "N/A" : safe(recorded.fitness);
  const hypotheticalScore = simulation?.assessment?.fitness == null
    ? "N/A" : safe(simulation.assessment.fitness);
  const delta = simulation ? fitnessDelta(recorded?.fitness,simulation.assessment.fitness) : null;
  const comparer = '<div class="comparison"><div><div class="twin-card-label">RECORDED BASELINE</div>' +
    '<div class="score-line"><strong>' + baselineScore +
    '</strong><span>/100 fitness</span></div><div class="pill-list">' +
    risks(recorded?.risk_flags || ["insufficient_data"]) + '</div></div>' +
    '<div><div class="twin-card-label">HYPOTHETICAL SCENARIO</div>' +
    '<div class="score-line"><strong>' + (simulation ? hypotheticalScore : "—") +
    '</strong><span>/100 fitness</span></div><div class="pill-list">' +
    (simulation ? risks(simulation.assessment?.risk_flags) : '<span class="muted">Not evaluated</span>') +
    '</div>' + (delta===null ? "" : '<p class="twin-delta">Score delta: ' + safe(delta) +
    " points (threshold-only changes may leave score unchanged)</p>") + '</div></div>';
  const snapshotStatus = unavailable(data,"snapshots",
    !recorded ? '<div class="notice-card"><strong>No recorded evidence yet.</strong> ' +
    "An authorized user must capture a snapshot before running a hypothetical scenario.</div>" : "");
  return layout("twin",
    (capability(state,"meta:observe") ? action("Capture current evidence","capture-snapshot","","soft") : "") +
    (capability(state,"meta:recommend") && recorded ?
      action("Propose recommendations","generate-recommendations","","soft") : ""),
    preface + '<div class="twin-grid"><section class="panel"><div class="panel-head"><h3>Scenario controls</h3><small>Not applied to AGO</small></div><div class="panel-body">' +
    snapshotStatus + '<label class="field-label" for="snapshot-select">Evidence snapshot</label>' +
    '<select id="snapshot-select"' + (!snapshots.length ? " disabled" : "") +
    '>' + (selectOptions || '<option value="">No snapshots available</option>') +
    '</select><div class="section-title"><h2>Hypothetical operating DNA</h2></div>' +
    ranges + '<div class="page-actions" style="justify-content:flex-start;padding-top:17px">' +
    (capability(state,"meta:simulate") ? action("Run comparison","compare-twin","","primary") : "") +
    action("Reset thresholds","reset-twin") + '</div></div></section>' +
    '<section class="panel"><div class="panel-head"><h3>Assessment</h3><small>Recorded vs hypothetical</small></div>' +
    '<div class="panel-body"><div class="split-actions"><span class="chip">' +
    (active?.source==="approved" ? "Human-approved DNA" : "Default baseline") +
    '</span><span class="text-mono">Snapshot ' + safe(shortId(recorded?.id || "none")) +
    '</span></div><div class="section-title"><h2>Fitness indicator</h2></div>' +
    comparer + '<div class="section-title"><h2>Safety interpretation</h2></div>' +
    '<div class="notice-card"><strong>Simulation only.</strong> The calculations use recorded task, QA and internal-credit values. A score of N/A means insufficient completed outcomes, not perfect performance. Threshold editing never changes actual DNA.</div></div></section></div>' +
    section("Evidence provenance") +
    panel("Snapshot integrity",'<div class="panel-body">' +
    '<div class="keyval"><span>Snapshot</span><strong class="text-mono">' +
    safe(recorded?.id || "None") + '</strong></div>' +
    '<div class="keyval"><span>SHA-256 evidence fingerprint</span><strong class="text-mono">' +
    safe(recorded?.digest || "None captured") + '</strong></div>' +
    '<div class="keyval"><span>Active DNA version</span><strong>' +
    safe(active?.version == null ? "Default baseline" : "v"+active.version) + '</strong></div>' +
    '<div class="keyval"><span>Authoritative execution</span><strong>None</strong></div>' +
    '<div class="page-actions" style="justify-content:flex-start">' +
    (recorded ? action("Verify evidence fingerprint","verify-snapshot") : "") +
    '</div></div>')) + renderCulture(data,state);
}
export function renderPage(page,data,state) {
  const fn = {
    overview:renderOverview,strategy:renderStrategy,governance:renderGovernance,
    organization:renderOrganization,knowledge:renderKnowledge,
    tools:renderTools,calendar:renderCalendar,twin:renderTwin,
  }[page];
  if (!fn) return '<div class="error-card">Unknown workspace</div>';
  return fn(data,state);
}
