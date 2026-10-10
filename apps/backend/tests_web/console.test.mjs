import test from "node:test";
import assert from "node:assert/strict";
import {
  SessionClient, ApiError, escapeHTML, uuid, validateProfile, fitnessDelta,
  shortId, dateText, formatRisk, statusTone,
} from "../ago/console/core.js";
import { renderPage, PAGES } from "../ago/console/views.js";

const TENANT = "12345678-1234-4234-8234-1234567890ab";
const ok = data => ({ ok: true, status: 200, json: async () => data });
const fail = (status, detail) => ({
  ok: false, status, json: async () => ({ detail }),
});
const mockState = (permissions = []) => ({
  me: { id: TENANT, permissions }, twin: {}, page: "overview",
});
const loaded = data => ({ status: "ok", data });
const forbidden = { status: "forbidden", data: null };

test("culture and reflection escape untrusted guidance and obey permissions", () => {
  const data={dna:loaded({profile:{qa_target_pct:85,backlog_limit:5,budget_alert_pct:80},
    charter:{mission:'<img src=x onerror=alert(1)>'}}),
    reflection:loaded({sample_count:2,status:'observed',reflection_findings:[
      {concern:'<script>bad</script>',proposal:'Review evidence'}]}),
    snapshots:loaded([]),dnarecords:loaded([]),recommendations:loaded([]),evaluations:loaded([])};
  const denied=renderPage('twin',data,mockState());
  assert.equal(denied.includes('<img'),false);
  assert.equal(denied.includes('<script>'),false);
  assert.equal(denied.includes('data-action="propose-company-dna"'),false);
  const allowed=renderPage('twin',data,mockState(['meta:dna:propose','meta:dna:read']));
  assert.equal(allowed.includes('data-action="propose-company-dna"'),true);
  assert.match(allowed,/Observed differences do not prove/);
});

test("untrusted string is always escaped before entering a template", () => {
  const payload = '<img src=x onerror="alert(1)"> & \' x';
  const output = escapeHTML(payload);
  assert.equal(output.includes("<img"), false);
  assert.match(output, /&lt;img/);
  assert.match(output, /&quot;/);
  assert.match(output, /&#39;/);
  assert.match(output, /&amp;/);
});

test("API URL and identity validation reject unexpected origins and SQL-like paths", async () => {
  assert.equal(uuid(TENANT), TENANT);
  for (const invalid of ["evil", TENANT+"'", "https://evil.example", "12345678"]) {
    assert.throws(() => uuid(invalid));
  }
  const client = new SessionClient({ fetchImpl: async () => ok({}) });
  await assert.rejects(client.request("https://evil.example/v1/tasks"));
  await assert.rejects(client.request("/v1//evil.example"));
  await assert.rejects(client.request("/v1/tasks#token"));
  await assert.rejects(client.request("/console/assets/"));
});

test("signed bearer is kept in client memory and never sent to foreign origin", async () => {
  const calls = [];
  const client = new SessionClient({ fetchImpl: async (path, options) => {
    calls.push({ path, ...options });
    return path === "/v1/sessions" ? ok({ access_token: "test-session-secret" })
      : ok([{ id: TENANT }]);
  } });
  await client.login({ tenant: TENANT, email: "user@example.test", password: "secret" });
  assert.equal(client.authenticated, true);
  assert.deepEqual(await client.request("/v1/tasks"), [{ id: TENANT }]);
  assert.equal(calls[0].headers.Authorization, undefined);
  assert.equal(calls[1].headers.Authorization, "Bearer test-session-secret");
  assert.equal(calls[1].credentials, "omit");
  assert.equal(calls[1].redirect, "error");
  assert.equal(calls[1].cache, "no-store");
  assert.equal(calls[1].mode, "same-origin");
  client.clear();
  assert.equal(client.authenticated, false);
  await client.request("/v1/tasks");
  assert.equal(calls[2].headers.Authorization, undefined);
});

test("HTTP 401 drops bearer and expires session without token reuse", async () => {
  let calls = 0, expired = 0;
  const client = new SessionClient({
    fetchImpl: async () => (++calls === 1)
      ? ok({ access_token: "session" }) : fail(401, "Invalid session"),
    onExpire: () => { expired++; },
  });
  await client.login({ tenant: TENANT, email: "x@y.test", password: "correct" });
  await assert.rejects(client.request("/v1/console/me"), e =>
    e instanceof ApiError && e.status === 401);
  assert.equal(client.authenticated, false);
  assert.equal(expired, 1);
});

test("403 is isolated per resource; other panels remain usable", async () => {
  const client = new SessionClient({
    fetchImpl: async path => path.endsWith("/brain/goals")
      ? fail(403,"Permission denied") : ok([{ id:TENANT }]),
  });
  const result = await client.readMany([
    ["goals","/v1/brain/goals"], ["tasks","/v1/tasks"],
  ]);
  assert.equal(result.goals.status,"forbidden");
  assert.equal(result.tasks.status,"ok");
  assert.equal(result.tasks.data.length,1);
});

test("hypothetical DNA rejects unknown keys, decimals, booleans and out-of-range values", () => {
  const profile = {
    qa_target_pct: 85, backlog_limit: 5, budget_alert_pct: 80,
  };
  assert.deepEqual(validateProfile(profile), profile);
  for (const candidate of [
    {...profile, disable_governance:true},
    {...profile, qa_target_pct: true},
    {...profile, backlog_limit: -1},
    {...profile, qa_target_pct: 85.4},
    {...profile, budget_alert_pct: 101},
  ]) assert.throws(() => validateProfile(candidate));
});

test("fitness never fabricates a score from insufficient evidence", () => {
  assert.equal(fitnessDelta(null, 99), null);
  assert.equal(fitnessDelta("12.25","11.25"),"-1.00");
  assert.equal(shortId(TENANT),"12345678…");
  assert.equal(dateText("invalid-date"),"—");
  assert.equal(formatRisk("qa_below_target"),"QA below target");
  assert.equal(statusTone("waiting_approval"),"warn");
});

test("eight workspaces exist; unauthorized data never displays fictional metrics", () => {
  assert.equal(Object.keys(PAGES).length,8);
  const overview = renderPage("overview", {
    score:forbidden, tasks:forbidden, approvals:forbidden, brief:forbidden,
  },mockState());
  assert.match(overview,/Not available to your role/);
  assert.match(overview,/—/);
  assert.doesNotMatch(overview,/100% healthy/i);
});

test("untrusted backend content is safe in organization, approvals, and knowledge", () => {
  const injection = '<script>alert(1)</script>';
  const state = mockState(["approval:decide","knowledge:review"]);
  const governance = renderPage("governance",{
    approvals:loaded([{ id:TENANT,action:injection,status:"pending",
      requester_id:"different",created_at:"2026-10-10T08:00:00Z" }]),
    tasks:loaded([{ id:TENANT,action:injection,status:"completed",assignee_id:TENANT }]),
    motions:loaded([]),
  },state);
  assert.doesNotMatch(governance,/<script>/);
  assert.match(governance,/&lt;script&gt;/);
  const knowledge = renderPage("knowledge",{
    verified:loaded([{id:TENANT,label:injection,statement:injection,source_ref:injection}]),
    pending:loaded([]),
  },state);
  assert.doesNotMatch(knowledge,/<script>/);
  assert.match(knowledge,/&lt;script&gt;/);
});

test("Digital Twin is explicitly hypothetical and cannot execute code or alter DNA", () => {
  const state = mockState(["meta:observe","meta:simulate"]);
  state.twin.profile = {
    qa_target_pct:85,backlog_limit:5,budget_alert_pct:80,
  };
  const html = renderPage("twin",{
    dna:loaded({profile:state.twin.profile,source:"baseline"}),
    snapshots:loaded([{id:TENANT,fitness:null,risk_flags:["insufficient_data"],
      digest:"a".repeat(64),created_at:"2026-10-10T08:00:00Z"}]),
  },state);
  assert.match(html,/Simulation only/i);
  assert.match(html,/Not applied to AGO/);
  assert.match(html,/N\/A/);
  assert.match(html,/data-action="compare-twin"/);
  assert.doesNotMatch(html,/automatic_execution.*true/);
});


test("governance reveals only authorized independently approved task actions", () => {
  const approved="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const own="bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  const cases={
    approvals:loaded([
      {id:approved,action:"internal:brief",requester_id:own,status:"approved"},
      {id:own,action:"private:change",requester_id:TENANT,status:"pending"},
    ]),
    tasks:loaded([
      {id:"cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        action:"internal:brief",status:"proposed",assignee_id:TENANT},
      {id:"dddddddd-dddd-4ddd-8ddd-dddddddddddd",
        action:"internal:brief",status:"waiting_approval",approval_id:approved,
        assignee_id:TENANT},
      {id:"eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
        action:"internal:brief",status:"completed",assignee_id:TENANT},
    ]),
    motions:loaded([]),reviews:loaded([]),
    qaqueue:loaded([{id:"eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      action:"internal:brief",status:"completed",assignee_id:TENANT}]),
  };
  const state=mockState([
    "approval:decide","task:create","approval:request",
    "agent:dispatch","qa:review",
  ]);
  const html=renderPage("governance",cases,state);
  assert.match(html,/data-action="task-request-approval"/);
  assert.match(html,/data-action="agent-run"/);
  assert.match(html,/data-action="qa-review"/);
  assert.doesNotMatch(html,/data-action="approve"/); // Owner cannot self-review.
});

test("enterprise tool dispatch button is hidden until the M2 request is approved", () => {
  const approvalId="aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const data={
    enrollments:loaded([]),rules:loaded([]),runs:loaded([]),
    tasks:loaded([{
      id:TENANT,action:"tool:scorecard",status:"waiting_approval",
      approval_id:approvalId,
    }]),
    approvals:loaded([{id:approvalId,status:"pending"}]),
  };
  const state=mockState(["tool:dispatch"]);
  assert.doesNotMatch(renderPage("tools",data,state),/data-action="tool-run"/);
  data.approvals=loaded([{id:approvalId,status:"approved"}]);
  assert.match(renderPage("tools",data,state),/data-action="tool-run"/);
});

test("calendar RSVP action appears only for an invited employee", () => {
  const state=mockState(["calendar:read","calendar:respond"]);
  const calendar={events:loaded([
    {id:TENANT,title:"Public event",status:"scheduled",invited:false,
      starts_at:"2026-10-12T08:00:00Z",ends_at:"2026-10-12T09:00:00Z"},
    {id:"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
      title:"Invited meeting",status:"scheduled",invited:true,
      starts_at:"2026-10-12T10:00:00Z",ends_at:"2026-10-12T11:00:00Z"},
  ])};
  const html=renderPage("calendar",calendar,state);
  assert.equal((html.match(/data-action="calendar-rsvp"/g)||[]).length,1);
});


test("Strategy activation waits for an independently approved real DB plan status", () => {
  const planId = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
  const approvalId = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
  const result = {
    goals: loaded([{id:TENANT,title:"Pilot objective",status:"active"}]),
    plans: loaded([{id:planId,goal_id:TENANT,approval_id:approvalId,
      title:"Pilot plan",status:"pending_approval"}]),
    approvals: loaded([{id:approvalId,status:"pending"}]),
  };
  const state = mockState(["brain:manage","brain:activate"]);
  const pending = renderPage("strategy",result,state);
  assert.match(pending,/pending approval/);
  assert.doesNotMatch(pending,/data-action="plan-activate"/);
  result.approvals = loaded([{id:approvalId,status:"approved"}]);
  assert.match(renderPage("strategy",result,state),/data-action="plan-activate"/);
  result.approvals = loaded([{id:approvalId,status:"rejected"}]);
  const rejected = renderPage("strategy",result,state);
  assert.match(rejected,/rejected/);
  assert.doesNotMatch(rejected,/data-action="plan-activate"/);
});
