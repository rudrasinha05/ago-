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
