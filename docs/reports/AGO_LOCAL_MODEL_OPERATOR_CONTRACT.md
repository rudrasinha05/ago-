# AGO optional local model runtime (founder-controlled)

**Scope:** AGO is personal/local development. The human founder exclusively
decides when the Windows laptop, AGO server and local model runtime run.
No Railway, cloud infrastructure, public endpoint or automatic startup exists.

This is a source-reviewed OPTIONAL integration contract. No model is downloaded,
installed, launched, used for inference or licensed by GitHub CI.

## 1. Consent and operating boundaries

The local inference adapter targets EXACTLY
`http://127.0.0.1:11434/api/generate`, with no API key, arbitrary endpoint,
shell commands, downloaded model, tool calling, web retrieval or function
execution. It uses a 30-second request limit, a bounded response size,
`stream:false`, a maximum 512 output tokens and `keep_alive:"0s"`.
The founder must manually choose and start the local Ollama-compatible
server if installed. Confirm Ollama binds to loopback, not a LAN/public IP.

Virtual AGO credit budgets still apply to each attempt; a running local model
uses the founder's laptop resources even though no paid API is called.
Project prompts may include confidential founder briefs: do not use public
model service forwarding or external proxies. A live project generation run
requires the founder's scoped authenticated task and independent QA.

## 2. Optional manual activation

Only after the founder has installed a locally usable model and manually
started the model server, set these shell-session variables:

```powershell
$env:AGO_LLM_PROVIDER = "ollama_local"
$env:AGO_ENABLE_LOCAL_MODELS = "true"
$env:AGO_ENABLE_PAID_MODELS = "false"
$env:AGO_LLM_MODEL = "<name-of-model-already-installed-locally>"
.\scripts\ago.ps1 serve
```

These variables do not download or start a model and do not authorize an
unapproved task. Existing `/v1/agents/tasks/{task_id}/run` requests still
require authenticated `agent:dispatch`, `task:execute`, approved matching
action, active plan, calendar, prior passing QA, available virtual credits
and allowlisted handler. Generated text is advisory; a founder/reviewer
must separately approve implementation.

To use a previously approved deterministic internal-brief task, the founder
can choose `.\scripts\ago.ps1 run-approved-internal`. This starts NO service,
prompts for a signed AGO local access token privately, shows eligible work in
dry-run mode, then requires a separate typed confirmation before action.
It does NOT call the LLM or perform GitHub writes.

For disabled local inference, unset `AGO_ENABLE_LOCAL_MODELS` and stop the
founder-started model server. Laptop off means zero AGO processing.

## 3. Evidence and suspension gate

Offline tests verify exact localhost transport and opt-in flags without
connecting to a real model. **Live model plan generation, output quality,
private-document minimization, hardware resource limits and independent human
review are not verified.** Keep AI detailed planning and full autonomous
software delivery marked **SUSPENDED** until those gates pass.

Do not put access tokens/API keys in chat, the repo, model prompts or CI logs.
