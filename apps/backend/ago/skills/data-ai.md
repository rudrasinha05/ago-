# Data and AI skills

## data.analysis
title: Analyze data and report findings
roles: employee, finance, pm
stages: discovery, quality
keywords: data, analysis, analyze, csv, spreadsheet, statistics, metrics, insight, report
source: AGO original (Claude, 2026-11-24)
---
1. Write the question first; decide what answer would change a decision. 2. Check the data: source, date range, missing values, duplicates, units. 3. Clean in code, never by hand, and keep the steps. 4. Start with simple counts, averages and trends before models. 5. Compare against a baseline or previous period. 6. Chart the key result clearly with labeled axes. 7. State findings, confidence and limits in plain words.

## data.dashboard
title: Design a metrics dashboard
roles: employee, pm, ceo
stages: architecture, implementation
keywords: dashboard, kpi, metrics, chart, analytics, visualization, report
source: AGO original (Claude, 2026-11-24)
---
1. Who looks at it and what decision they make. 2. 3-6 key numbers at the top with change vs last period. 3. One chart per question; line for time, bar for comparison. 4. Same units and time range everywhere. 5. Show data freshness and source. 6. Drill-down only where action follows. 7. Remove any number nobody acts on.

## ai.prompt-engineering
title: Write prompts for language models
roles: employee, cto
stages: architecture, implementation
keywords: prompt, llm, gpt, claude, gemini, ollama, model, ai, instruction, chatbot
source: AGO original (Claude, 2026-11-24)
---
1. State the role, the task and the exact output format. 2. Give the needed context and nothing else. 3. Show one short example of a good answer. 4. Mark untrusted text as quoted data, never instructions. 5. Ask for structured output (JSON schema) when code reads it. 6. Set limits: length, language, what to do when unsure. 7. Test with tricky inputs and keep prompts in version control.

## ai.rag
title: Retrieval-augmented generation (RAG)
roles: employee, cto
stages: architecture, implementation
keywords: rag, retrieval, embeddings, vector, search, knowledge, base, documents, chunk
source: AGO original (Claude, 2026-11-24)
---
1. Split documents into meaningful chunks (by heading, 300-800 tokens) with overlap. 2. Store embeddings plus source, date and access rights. 3. Retrieve only what the user may see. 4. Rerank and keep the top few chunks. 5. Tell the model to answer only from the chunks and cite them. 6. Say "not found" when nothing matches. 7. Evaluate with a fixed question set and track accuracy.

## ai.evaluation
title: Evaluate an AI feature
roles: qa, employee, cto
stages: quality
keywords: evaluation, eval, ai, model, accuracy, benchmark, hallucination, quality
source: AGO original (Claude, 2026-11-24)
---
1. Build a test set of real inputs with expected answers (50+). 2. Include hard and adversarial cases. 3. Define scoring: exact, rubric, or human rating. 4. Run every model or prompt change against the same set. 5. Track accuracy, refusal, cost and latency together. 6. Read failures, do not only count them. 7. Ship only when the score beats the current version.

## ai.agent-design
title: Design an AI agent workflow
roles: cto, employee, risk
stages: architecture
keywords: agent, agents, autonomous, workflow, tool, tools, multi-agent, orchestration
source: AGO original (Claude, 2026-11-24)
---
1. Break the job into steps with clear inputs and outputs. 2. Give each agent one role and the fewest tools it needs. 3. Every action that changes the world needs a check or an approval. 4. Bound loops: max steps, time and cost. 5. Record each step's input, output and model as evidence. 6. Plan failures: retry, escalate to a human, stop. 7. Measure task success, not activity.

## data.ml-basics
title: Machine learning model, end to end
roles: employee, cto
stages: architecture, implementation
keywords: machine, learning, ml, model, training, dataset, prediction, classification, regression
source: AGO original (Claude, 2026-11-24)
---
1. Check that a simple rule or heuristic is not enough. 2. Define the target and a baseline. 3. Split data into train/validation/test without leakage (time-based if needed). 4. Start with a simple model; tune later. 5. Choose a metric that matches the cost of errors. 6. Check fairness across groups. 7. Monitor live accuracy and retrain on drift.
