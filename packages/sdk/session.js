/** Security-conscious shared console primitives. No persistent browser storage. */
export const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;

export function escapeHTML(input) {
  return String(input ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}
export const safe = escapeHTML;
export function uuid(input) {
  if (!UUID_RE.test(String(input))) throw new Error("Invalid organization identifier");
  return String(input);
}
export function shortId(value) {
  const str = String(value ?? "");
  return str.length > 12 ? str.slice(0, 8) + "…" : str;
}
export function num(value, fallback = "—") {
  return typeof value === "number" && Number.isFinite(value)
    ? new Intl.NumberFormat("en-IN").format(value)
    : fallback;
}
export function amount(value) {
  const number = Number(value);
  return value !== null && value !== undefined && String(value) !== ""
    && Number.isFinite(number) ? number.toLocaleString("en-IN", {
      minimumFractionDigits: 0, maximumFractionDigits: 2,
    }) : "—";
}
export function dateText(value) {
  if (!value) return "—";
  const timestamp = new Date(value);
  return Number.isNaN(timestamp.valueOf()) ? "—" : timestamp.toLocaleString(
    undefined, { year: "numeric", month: "short", day: "numeric",
      hour: "2-digit", minute: "2-digit" },
  );
}
export function statusTone(status) {
  const key = String(status ?? "").toLowerCase();
  if (["approved","active","verified","completed","endorsed","passed","accepted"].includes(key))
    return "good";
  if (["pending","proposed","draft","running","waiting_approval","requested","scheduled","open"].includes(key))
    return "warn";
  if (["rejected","failed","cancelled","disabled","uncertain","declined"].includes(key))
    return "bad";
  return "";
}
export function percent(value) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.min(100, Math.max(0, n)) : 0;
}
export function validateProfile(input) {
  const allowed = {
    qa_target_pct: [50, 100],
    backlog_limit: [0, 10000],
    budget_alert_pct: [1, 100],
  };
  if (!input || typeof input !== "object" || Array.isArray(input)
    || Object.keys(input).sort().join(",") !== Object.keys(allowed).sort().join(","))
    throw new Error("Digital Twin thresholds have an invalid structure");
  const result = {};
  for (const [key, [min, max]] of Object.entries(allowed)) {
    const value = Number(input[key]);
    if (!Number.isInteger(value) || value < min || value > max
      || input[key] === true || input[key] === false)
      throw new Error("Invalid Digital Twin threshold: " + key);
    result[key] = value;
  }
  return result;
}
export function fitnessDelta(baseline, candidate) {
  if (baseline === null || candidate === null || baseline === undefined
    || candidate === undefined || baseline === "" || candidate === "")
    return null;
  const a = Number(baseline), b = Number(candidate);
  return Number.isFinite(a) && Number.isFinite(b) ? (b - a).toFixed(2) : null;
}
export function formatRisk(flag) {
  const labels = {
    insufficient_data: "Not enough verified outcomes",
    qa_below_target: "QA below target",
    backlog_over_limit: "Backlog above limit",
    budget_alert: "Internal credit threshold reached",
    high_failure_rate: "High failure rate",
    budget_shortfall: "Simulated budget shortfall",
  };
  return labels[flag] || String(flag ?? "").replaceAll("_", " ");
}
export class ApiError extends Error {
  constructor(status, message) {
    super(message || "Request failed");
    this.name = "ApiError";
    this.status = status;
  }
}
export class SessionClient {
  #token = "";
  #generation = 0;
  #pending = new Set();
  constructor({ fetchImpl = globalThis.fetch?.bind(globalThis), onExpire = () => {} } = {}) {
    if (typeof fetchImpl !== "function") throw new Error("Fetch required");
    this.fetchImpl = fetchImpl;
    this.onExpire = onExpire;
  }
  get authenticated() { return Boolean(this.#token); }
  clear() { this.#token = ""; this.#generation++; for (const controller of this.#pending) controller.abort(); this.#pending.clear(); }
  async logout() {
    const token = this.#token;
    this.clear();
    if (!token) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await this.fetchImpl("/v1/console/logout", {
        method: "POST", headers: { Accept: "application/json", Authorization: "Bearer " + token },
        signal: controller.signal, cache: "no-store", credentials: "omit",
        redirect: "error", mode: "same-origin",
      });
      if (!response.ok && response.status !== 401) throw new ApiError(response.status, "Session revocation unavailable");
    } finally { clearTimeout(timeout); }
  }
  async login({ tenant, email, password }) {
    uuid(tenant);
    if (!email || !password) throw new Error("Work email and password are required");
    this.clear();
    const session = await this.request("/v1/sessions", {
      method: "POST", body: { tenant_id: tenant, email, password },
    });
    if (typeof session?.access_token !== "string" || !session.access_token)
      throw new Error("Invalid session response");
    this.#token = session.access_token;
  }
  async request(path, { method = "GET", body, timeoutMs = 15000 } = {}) {
    if (typeof path !== "string" || !path.startsWith("/v1/")
      || path.includes("//") || path.includes("\\") || path.includes("#"))
      throw new Error("API requests must use a same-origin /v1 route");
    const generation = this.#generation;
    const controller = new AbortController();
    this.#pending.add(controller);
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (this.#token) headers.Authorization = "Bearer " + this.#token;
    try {
      const response = await this.fetchImpl(path, {
        method, headers, body: body === undefined ? undefined : JSON.stringify(body),
        signal: controller.signal, cache: "no-store", credentials: "omit",
        redirect: "error", mode: "same-origin",
      });
      const payload = await response.json().catch(() => ({}));
      if (generation !== this.#generation) throw new ApiError(0, "Session changed");
      if (!response.ok) {
        if (response.status === 401 && path !== "/v1/sessions") {
          this.clear();
          this.onExpire();
        }
        const detail = typeof payload.detail === "string"
          ? payload.detail : "Request denied or unavailable";
        throw new ApiError(response.status, detail);
      }
      return payload;
    } catch (error) {
      if (error.name === "AbortError") throw new ApiError(0, "Request timed out");
      throw error;
    } finally {
      clearTimeout(timeout);
      this.#pending.delete(controller);
    }
  }
  async readMany(entries) {
    const results = await Promise.all(entries.map(async ([key, path]) => {
      try {
        return [key, { status: "ok", data: await this.request(path) }];
      } catch (error) {
        return [key, {
          status: error.status === 403 ? "forbidden"
            : error.status === 401 ? "unauthenticated" : "error",
          message: String(error.message || "Unavailable"),
          data: null,
        }];
      }
    }));
    return Object.fromEntries(results);
  }
}
export function resource(result, key) {
  return result?.[key]?.status === "ok" ? result[key].data : null;
}
export function errorMessage(result, key) {
  const entry = result?.[key];
  if (!entry || entry.status === "ok") return "";
  return entry.status === "forbidden" ? "Not available to your role"
    : entry.status === "unauthenticated" ? "Session expired"
      : entry.message || "Unable to load";
}
