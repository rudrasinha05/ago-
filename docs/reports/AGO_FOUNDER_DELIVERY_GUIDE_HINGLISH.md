# AGO Founder Guide — Ek Prompt Se Project Delivery (Hinglish)

**Audience:** AGO ka Founder, Windows par personal/local use.  
**Source:** AGO ka current implemented software path; production acceptance nahi.  
**Branch:** `develop`. Public launch, cloud subscription aur Play Store ki koi zarurat nahi.

## Founder ko kya karna hai?

**Normally sirf AGO ka dashboard use karo.** Company Map mein *Project Delivery*
section kholkar apne private GitHub projects ka real evidence dekh sakte ho.
Bina approved repository ke dashboard "No approved GitHub project" dikhayega.
Aisa hona error ya code-completion ka proof nahi hai.

Ek expected project journey:

1. **Tum project ka idea aur requirements bhejte ho.** AGO project plan aur
   zimmedar manager establish karta hai. Plan review aur AI execution ke
   liye jo authorization zaruri hai, woh alag track hota hai.
2. **CEO, Board aur AI employees project par kaam karte hain.** Local Ollama
   engine actually enabled aur running hona chahiye. Brain sirf real
   persisted task activity dikhata hai; animation successful coding ka
   proof nahi.
3. **Generated code private folder mein review ke liye aata hai.**
   Original source/tests ko offline Docker mein chalakar actual PASS/FAIL
   receipt banega. Failure par source-only repair proposal aur retest hai.
4. **Independent human QA.** Qualified doosra human reviewer code, original
   requirements aur test report dekhkar signed PASS/FAIL deta hai. AI khud
   apne kaam ko PASS certify nahi kar sakta.
5. **GitHub handover.** Original QA evidence aur private GitHub repo ke
   liye Founder-approved operation independent enterprise review mein jata
   hai. Real `develop` commit ke baad required GitHub check runs PASS
   hone par **Draft Pull Request** create ho sakta hai.
6. **Final delivery report.** Commit SHA, actual draft PR URL, required CI
   aur independent QA evidence available hone par report truthful hogi.
   Draft PR ko release ya automatic merge **mat samjho**.

## 'Prepare / Submit / Apply / Execute' ka matlab

- **Prepare:** verified code/CI aur QA se reviewable *draft* taiyar.
- **Submit:** draft ko company governance review inbox mein bhejna.
- **Apply:** independent human approval ke baad approved action ko AGO mein register.
- **Execute:** final authorized GitHub action (commit ya draft PR) **ek baar** run.

Ye administrative stages safety ke liye hain; Founder ko manually har command
type karna AGO ka final UX target nahi. **Company Map → Project Delivery**
mein available signed operations aur independent review status dikhenge.
Approval dena ek authorized human ka kaam hai; actual model generation/QA,
GitHub owner credential aur network connection ko UI assume nahi karta.

## Project Delivery Center ka factual meaning

- **Private repository verified:** bound GitHub server ne private visibility confirm ki.
- **Waiting independent approval:** authorized human ne abhi APPROVE nahi kiya.
- **Applied to AGO:** action recorded, lekin **GitHub par abhi nahi gaya**.
- **Verified commit:** AGO ke database mein successful actual dispatch ka
  40-digit commit SHA record hua.
- **Verified draft PR:** GitHub dispatch receipt mein exact PR number,
  expected branch HEAD aur target private repo URL confirm hain.
- **Unknown/uncertain:** action ke final outcome ka proof nahi. Automatic
  retry disabled; actual GitHub aur AGO recorded marker inspect karna hai.

## Windows commands kisliye rakhe hain?

`ago.ps1`, `ago-repair.ps1` aur `ago-pr.ps1` **advanced local operator
fallbacks** hain—jab CLI-based source review, model diagnosis, backup,
QA ya connection reconciliation chahiye. Inko roz chalana Founder ka
normal kaam nahi. Jo actual device/provider access missing hai usko
ChatGPT ke GitHub source-code commits se replace nahi kiya ja sakta.

## Real Ollama run se Docker QA — naya Founder shortcut

Prerequisites: active Founder-approved AGO implementation stage, correctly appointed seven AI roles, manually started local Ollama + AGO backend, and an existing offline Docker `python:3.11-slim` image. No auto-install/download/service startup.

Server terminal (use the model you actually installed):

```powershell
$env:AGO_ENVIRONMENT='development'
$env:AGO_LLM_PROVIDER='ollama_local'
$env:AGO_ENABLE_LOCAL_MODELS='true'
$env:AGO_ENABLE_PAID_MODELS='false'
$env:AGO_LOCAL_COMPANY_CHAIN='true'
$env:AGO_LOCAL_FULL_BOARD_REVIEW='true'
$env:AGO_LOCAL_ENGINEERING_CANDIDATES='true'
$env:AGO_LLM_MODEL='qwen2.5-coder:1.5b'
.\scripts\ago.ps1 serve
```

Separate PowerShell terminal: run a **previously approved** task, then enter its actual completed run UUID at the bridge prompt.

```powershell
.\scripts\ago.ps1 run-approved-engineering
# After the real AGO run reports its completed run UUID:
$run = 'PASTE_COMPLETED_RUN_UUID'
$attempt = [guid]::NewGuid().ToString('N')
New-Item -ItemType Directory -Force "$HOME\.ago\candidate_exports", "$HOME\.ago\delivery_runs" | Out-Null
$export = "$HOME\.ago\candidate_exports\run-$attempt.json"
$stage = "$HOME\.ago\delivery_runs\stage-$attempt"
$qa = "$HOME\.ago\delivery_runs\qa-$attempt.json"
python scripts/ago_live_to_qa.py --run-id $run --export $export --staged-directory $stage --qa-packet $qa
# Inspect the exact generated source and tests in AGO, then copy the preview SHA-256:
$sha = 'PASTE_PREVIEW_CANDIDATE_SHA256'
python scripts/ago_live_to_qa.py --run-id $run --export $export --staged-directory $stage --qa-packet $qa --apply --expected-candidate-sha256 $sha --confirm-export EXPORT_APPROVED_AI_CANDIDATE --confirm-docker STAGE_TEST_AND_PREPARE_QA
```

The bridge uses a signed Founder session to preview the exact persisted Board-cleared run without writing files, prints the candidate SHA-256, then asks you to inspect the actual source and tests in AGO. To continue, retype that SHA-256 and provide two **separate** exact consent phrases for private export and offline Docker testing. Changed run identity or source digest blocks execution.

Raw candidate source is saved privately in `~/.ago/candidate_exports`; staging and original Docker test evidence remain in `~/.ago/delivery_runs`, outside the Git checkout. Docker is network-disabled, read-only and non-root. Failed tests produce **no** QA request. Passing tests produce only a **pending human QA packet**, never self-approval or GitHub write.

Independent human review and governed GitHub submission remain separate:

```powershell
.\scripts\ago.ps1 review-tested-candidate
.\scripts\ago.ps1 prepare-github-draft
.\scripts\ago.ps1 submit-github-proposal
.\scripts\ago.ps1 apply-github-proposal
.\scripts\ago.ps1 execute-github-commit
```

These operations require the authenticated separately appointed reviewer, exact source/QA receipts, Founder credentials and independently approved GitHub scope. A commit is NOT a verified Draft PR or published release. Local synthetic fixtures and GitHub CI do not establish one real Ollama-produced market-ready delivery; the owner must verify the actual device evidence and final provider SHA/PR.
## Kya complete hone ka claim **nahi** hai

- Local owner laptop par real end-to-end model coding run **not verified**.
- Saare 48 P0–P2 acceptance items **not completed**.
- Real independent reviewer ne exact user project accept kiya **not verified**.
- AGO ne khud project ka successfully private GitHub draft PR banaya
  **not verified**.
- User product automatically market-ready/published **nahi**.

Jab tak actual source, isolated test results, human review aur provider-side
commit/PR evidence nahi aate, dashboard blocked/incomplete dikhayega.
Sirf green unit tests aur attractive company animation se delivered project
ka final status nahi banega.
