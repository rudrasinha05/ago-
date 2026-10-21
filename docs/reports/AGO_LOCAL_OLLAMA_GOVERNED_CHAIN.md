# AGO: founder-operated local Ollama, four-role governed task execution

**Status:** implementation/CI acceptance for localhost development; not an
assertion that Ollama is installed or running on the founder's Windows machine.
There are NO cloud deployments or auto-start worker requirements.

## Hardware profile and chosen local model

- Existing laptop: Lenovo IdeaPad Gaming 3 15IHU6; NVIDIA GTX 1650 **4 GB VRAM**, Windows 11.
- Default: **`qwen2.5:3b`**, quantized Ollama distribution, approximately
  **1.9 GB download/model**. The 4 GB GPU may partially offload it depending
  on available VRAM, concurrent apps, CUDA compatibility and current RAM.
- Fallback: **`qwen2.5:1.5b`** (~986 MB) for lower memory pressure.
- The installed `qwen2.5-coder:1.5b` code-focused model is also supported for manually authorized AGO localhost inference. Use the exact installed model tag; its software-engineering ability remains subject to model-output and QA tests.
- Do **not** silently choose 7B/14B models or use `qwen2.5` without `:3b`,
  since the default may require >4 GB VRAM. Leave extra headroom for Windows
  and browser processes. Actual GPU share/tokens per second require a local test.
- Runtime: single sequential process, 4 bounded inference passes, 2,048-token
  context per request, maximum 384 generated tokens, per-pass timeout 60s,
  no tools, outbound HTTP, repository writes, spawning or model downloads.
  Model remains cached for at most 90s between steps (can be unloaded by Ollama
  after the configured idle period). The founder alone stops/starts Ollama.
- All prompt/result text is local-only. `AGO_LLM_API_KEY` is NOT required.
  Paid-model mode remains entirely separate, opt-in, and **not** fallback.

Official documentation:
- https://ollama.com/download/windows
- https://ollama.com/library/qwen2.5
- https://docs.ollama.com/api

## Human-initiated setup (Windows PowerShell)

Install Ollama for Windows manually from the official download page.
Ollama must not be configured by AGO to start with Windows, wake the laptop or
bind to a public interface. If the Ollama desktop installer enables a tray
auto-start or login startup, disable it in Windows Startup Apps to retain
founder start/stop authority. Use the terminal, with Ollama explicitly started
by the founder, to download a model once:

```powershell
ollama pull qwen2.5:3b
ollama list
# For a lower-memory profile, explicitly choose instead:
# ollama pull qwen2.5:1.5b
# No app should automatically execute these installation/pull commands.
```

For a separately and manually started local Ollama server if not running:
`ollama serve`. Keep `OLLAMA_HOST` restricted to `127.0.0.1:11434`.
Verify: `Invoke-RestMethod http://127.0.0.1:11434/api/tags`.
Run the built-in **read-only** readiness check from the repo root:
`./scripts/ago-ollama-check.ps1 -Model qwen2.5:3b`.
It never starts or downloads a model.
AGO never executes `ollama serve`, `ollama pull` or OS startup tasks.

Before starting AGO from the **same** founder-controlled PowerShell environment:

```powershell
$env:AGO_LLM_PROVIDER='ollama_local'
$env:AGO_ENABLE_LOCAL_MODELS='true'
$env:AGO_LOCAL_COMPANY_CHAIN='true'
$env:AGO_LLM_MODEL='qwen2.5:3b'
$env:AGO_ENABLE_PAID_MODELS='false'
.\scripts\ago.ps1 serve
```

The values are session-scoped; AGO does NOT persist a Windows service or
system-wide environment variable. Close the PowerShell process or Ctrl+C to
stop the AGO backend. The laptop ON/OFF schedule belongs only to the founder.

## Actual scope of the four roles

This replaces the normal **`internal:brief` handler ONLY** when all local
opt-ins above are explicitly set. The `POST /v1/agents/tasks/{task_id}/run`
API still requires a signed authenticated caller with `agent:dispatch` and
the **previously approved** task; `AgentRuntime/TaskStore` performs the normal
tenant, task-status, approval-action, worker and credit-budget gates.

A project-linked **discovery task** must be part of an **active founder-approved**
plan. Project brief is founder-confidential, so the caller must be the
authenticated human founder. The four distinct AI identities must already
exist in the tenant:

1. CEO: actual AI employee appointed by the founder to **Strategy & Vision**
   board seat
2. CTO: distinct AI employee appointed by the founder to
   **Technology Oversight** board seat
3. PM: distinct accountable project manager from
   `ago_founder_project_lead.accountable_manager_id`
4. Employee: distinct AI assignee of the approved discovery task

No roles are invented from string labels. Missing seat, draft plan, repeated
person, non-AI principal, changed tenant or mismatched project/task fail
closed BEFORE the task is consumed. Board appointments are evidence of
identity, **not** an authorization to hire, approve, review or publish.

The four calls happen sequentially:
CEO business goals → CTO bounded architecture → PM work package → assigned
employee internal deliverable. Each receives bounded excerpts of prior output,
each result is tagged to the real employee UUID and stored inside the one
already-governed agent-run result. The model's generated text is untrusted,
is NOT itself a reviewed project stage, a real GitHub patch or a QA verdict.
If the local server is absent or a call times out, the ordinary safe agent
failure recording applies. **No automatic replay** after an unknown outcome.

The result contains explicit `requires_human_qa=true`,
`human_qa_approved=false`, `github_commits_created=false` and
`project_released=false`. An independent authorized human reviewer
must assess the deliverable before founder release.

A local virtual-credit charge of 4 units per attempt reserves the four
role passes; configure the existing bounded local credit budget before use.
No real payment, cloud service or paid-provider fallback is needed.

## Acceptance evidence / current limits

Unit tests: actual distinct employee identity mapping, active founder plan,
worker task binding, opt-in handler override, no external tool execution and
fail-closed missing personnel, with fake Ollama HTTP results.

The CI can verify model adapter code and PostgreSQL authorization. It cannot
confirm the founder has manually installed Ollama, pulled the model, granted a
local credit budget, staffed four distinct AI roles, or benchmarked GTX 1650
performance. A **real laptop smoke test** is separate and must never be
reported as passed by mocked CI.

**Important:** this is **governed local drafting execution**, NOT
self-directed code editing, PR creation, human replacement, continuous
background operation, paid marketing or market-ready product publishing.
Those capabilities need their own separate approved task/tools/QA evidence.
