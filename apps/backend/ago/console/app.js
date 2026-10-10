/** AGO M9 first-party control center. Browser token is deliberately tab-memory only. */
import { SessionClient, resource, validateProfile } from "./core.js";
import { PAGES, renderPage } from "./views.js";
import { handleAction } from "./actions.js";

const auth = document.getElementById("auth");
const workspace = document.getElementById("workspace");
const form = document.getElementById("login-form");
const screen = document.getElementById("screen");
const nav = document.getElementById("primary-nav");
const sidebar = document.getElementById("sidebar");
const shade = document.getElementById("mobile-shade");
const dialog = document.getElementById("action-dialog");
const toastBox = document.getElementById("toast");

let toastTimer;
const state = {
  page: "overview", me: null, data: {}, twin: {},
  epoch: 0, tenant: "", lastLoaded: null,
};

function toast(message, danger = false) {
  toastBox.textContent = String(message || "Action completed");
  toastBox.classList.toggle("bad", Boolean(danger));
  toastBox.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { toastBox.hidden = true; }, 5500);
}
function localLogout(message = "") {
  state.epoch++;
  api.clear();
  state.me = null;
  state.data = {};
  state.twin = {};
  state.tenant = "";
  state.lastLoaded = null;
  closeMobile();
  if (dialog.open) dialog.close();
  workspace.hidden = true;
  auth.hidden = false;
  form.querySelector('[name="password"]').value = "";
  form.querySelector('[name="password"]').focus();
  if (message) toast(message, true);
}
const api = new SessionClient({
  onExpire: () => localLogout("Your session expired. Sign in again."),
});
function can(permission) {
  return Array.isArray(state.me?.permissions) &&
    state.me.permissions.includes(permission);
}
function setMobile(open) {
  sidebar.classList.toggle("open", open);
  shade.hidden = !open;
  document.getElementById("menu-button").setAttribute(
    "aria-expanded", String(open),
  );
}
function closeMobile() { setMobile(false); }
function setNavigation(page) {
  nav.querySelectorAll("[data-page]").forEach(button => {
    const active = button.dataset.page === page;
    button.classList.toggle("active", active);
    if (active) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  document.getElementById("breadcrumb").textContent = PAGES[page].title;
}

function dateRange() {
  const start = new Date(Date.now() - 24 * 3600_000);
  const end = new Date(Date.now() + 30 * 24 * 3600_000);
  return "/v1/operations/calendar?start=" + encodeURIComponent(start.toISOString()) +
    "&end=" + encodeURIComponent(end.toISOString());
}
function endpoints(page) {
  const entries = {
    overview: [
      ["score","/v1/insights/scorecard"],
      ["tasks","/v1/tasks"],
      ["approvals","/v1/governance/approvals"],
      ["brief","/v1/meta/brief"],
    ],
    strategy: [
      ["goals","/v1/brain/goals"],
      ["plans","/v1/brain/plans"],
    ],
    governance: [
      ["approvals","/v1/governance/approvals"],
      ["tasks","/v1/tasks"],
      ["motions","/v1/council/motions"],
      ["reviews","/v1/console/task-reviews"],
    ],
    organization: [
      ["departments","/v1/organization/departments"],
    ],
    knowledge: [
      ["verified","/v1/knowledge/nodes"],
      ["pending","/v1/knowledge/pending"],
    ],
    tools: [
      ["enrollments","/v1/tools/enrollments"],
      ["rules","/v1/tools/automation/rules"],
      ["runs","/v1/tools/runs"],
      ["tasks","/v1/tasks"],
      ["approvals","/v1/governance/approvals"],
    ],
    calendar: [["events", dateRange()]],
    twin: [
      ["dna","/v1/meta/dna/active"],
      ["snapshots","/v1/meta/snapshots"],
    ],
  };
  return entries[page] || [];
}
function showLoading() {
  screen.innerHTML = '<div class="loading-screen"><div class="spinner"></div>' +
    " Loading live organizational records…</div>";
}
function showPage() {
  if (!api.authenticated || !state.me) return;
  screen.innerHTML = renderPage(state.page, state.data, state);
  document.getElementById("last-refresh").textContent = state.lastLoaded
    ? "Synced " + state.lastLoaded.toLocaleTimeString([], {
      hour: "2-digit", minute: "2-digit",
    }) : "Not synced";
}
async function refreshCurrent({ focus = false } = {}) {
  if (!api.authenticated) return;
  const epoch = ++state.epoch;
  const page = state.page;
  showLoading();
  const result = await api.readMany(endpoints(page));
  if (epoch !== state.epoch || !api.authenticated || page !== state.page) return;
  if (page === "organization" && result.departments?.status === "ok") {
    const departments = resource(result, "departments");
    const entries = await Promise.all((Array.isArray(departments) ? departments : []).map(
      async department => {
        try {
          return [department.id, await api.request(
            "/v1/organization/employees?department_id=" +
            encodeURIComponent(department.id),
          )];
        } catch (error) {
          return [department.id, null];
        }
      },
    ));
    if (epoch !== state.epoch || !api.authenticated) return;
    const failed = entries.some(([, team]) => !Array.isArray(team));
    result.employees = failed ? {
      status: "forbidden", data: null,
      message: "Some personnel lists are not available",
    } : { status: "ok", data: Object.fromEntries(entries) };
  }
  if (page === "twin") {
    const approved = resource(result, "dna");
    const snapshots = resource(result, "snapshots");
    if (!state.twin.profile && approved?.profile) {
      state.twin.profile = { ...approved.profile };
    }
    if (Array.isArray(snapshots) && snapshots.length) {
      if (!snapshots.some(x => x.id === state.twin.snapshotId)) {
        state.twin.snapshotId = snapshots[0].id;
        state.twin.simulation = null;
      }
    } else {
      state.twin.snapshotId = "";
      state.twin.simulation = null;
    }
  }
  state.data = result;
  state.lastLoaded = new Date();
  showPage();
  if (focus) screen.focus({ preventScroll: true });
}
async function goPage(page) {
  if (!(page in PAGES) || !api.authenticated) return;
  state.page = page;
  state.data = {};
  closeMobile();
  setNavigation(page);
  await refreshCurrent({ focus: true });
}
function initializeWorkspace() {
  const user = state.me;
  const initials = String(user?.display_name || user?.email || "AG")
    .trim().split(/\s+/).slice(0,2).map(x => x[0] || "").join("").toUpperCase();
  document.getElementById("tenant-label").textContent = state.tenant.slice(0,8) + "…";
  document.getElementById("side-identity").textContent =
    user.display_name || user.email || "AGO member";
  document.getElementById("side-avatar").textContent = initials;
  document.getElementById("top-avatar").textContent = initials;
  auth.hidden = true;
  workspace.hidden = false;
}
form.addEventListener("submit", async event => {
  event.preventDefault();
  const submit = document.getElementById("login-button");
  const errorArea = document.getElementById("login-error");
  errorArea.hidden = true;
  submit.disabled = true;
  const fields = new FormData(form);
  const tenant = String(fields.get("tenant") || "").trim();
  const email = String(fields.get("email") || "").trim();
  const password = String(fields.get("password") || "");
  try {
    await api.login({ tenant, email, password });
    state.tenant = tenant;
    state.me = await api.request("/v1/console/me");
    initializeWorkspace();
    form.querySelector('[name="password"]').value = "";
    toast("Connected to AGO. Governance safeguards are active.");
    await goPage("overview");
  } catch (error) {
    api.clear();
    state.me = null;
    workspace.hidden = true;
    auth.hidden = false;
    errorArea.textContent = error?.status === 401
      ? "The organization ID, email or password was not accepted."
      : String(error.message || "Unable to sign in");
    errorArea.hidden = false;
  } finally {
    submit.disabled = false;
  }
});
document.getElementById("signout").addEventListener("click", async () => {
  try {
    if (api.authenticated) await api.request("/v1/console/logout", { method:"POST" });
  } catch {
    // Local credential disposal must occur even if the server is unavailable.
  } finally {
    localLogout();
    toast("Signed out. Browser session cleared.");
  }
});
document.getElementById("refresh").addEventListener("click", () => {
  void refreshCurrent({ focus: true });
});
document.getElementById("menu-button").addEventListener("click", () => {
  setMobile(!sidebar.classList.contains("open"));
});
shade.addEventListener("click", closeMobile);
nav.addEventListener("click", event => {
  const target = event.target.closest("[data-page]");
  if (target) void goPage(target.dataset.page);
});
screen.addEventListener("click", event => {
  const button = event.target.closest("button[data-action]");
  if (!button || button.disabled) return;
  void handleAction(button.dataset.action, button.dataset.id || "", {
    api, state, can, refreshCurrent, goPage, showPage, toast, dialog,
  }).catch(error => toast(error.message || "Action failed", true));
});
screen.addEventListener("input", event => {
  const control = event.target.closest("[data-twin-field]");
  if (!control) return;
  const key = control.dataset.twinField;
  const profile = { ...(state.twin.profile || resource(state.data,"dna")?.profile) };
  profile[key] = Number(control.value);
  try {
    state.twin.profile = validateProfile(profile);
    state.twin.simulation = null;
    const output = document.getElementById("output-" + key);
    if (output) output.textContent = control.value +
      (key === "backlog_limit" ? " tasks" : "%");
  } catch (error) {
    toast(error.message, true);
  }
});
screen.addEventListener("change", event => {
  if (event.target.matches("[data-twin-field]")) {
    showPage(); // Discard stale comparison after the user finishes dragging.
  }
  if (event.target.id === "snapshot-select") {
    state.twin.snapshotId = event.target.value;
    state.twin.simulation = null;
    showPage();
  }
});
dialog.addEventListener("click", event => {
  if (event.target === dialog || event.target.closest("[data-modal-close]")) {
    dialog.close();
  }
});
