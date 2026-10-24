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
