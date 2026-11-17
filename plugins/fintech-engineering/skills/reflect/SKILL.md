---
name: reflect
description: Review a completed or difficult fintech engineering task and propose evidence-backed improvements to skills, repository instructions, scripts, tests, or CI. Use after delivery problems or repeated friction; never change shared policy automatically.
---

# Reflect

Turn demonstrated workflow friction into reviewable improvements without overfitting one unusual task.

## Gather evidence

Inspect the final requirements, timeline, decisions, failures, retries, test evidence, review findings, and resulting pull request. Distinguish product defects from workflow, tooling, instruction, and environment problems.

## Propose

Read [references/proposal-template.md](references/proposal-template.md). For each candidate improvement:

1. Cite the observed failure or repeated cost.
2. Identify the narrowest durable enforcement point.
3. Prefer a test, type, lint rule, or deterministic script over prose when the behavior is machine-checkable.
4. Put repository-specific knowledge in that repository; put repeated cross-repository workflow in the shared plugin.
5. Explain the downside, maintenance cost, and cases where the proposal should not apply.
6. Classify it as accept, reject, backlog, or needs more evidence.

Do not edit `AGENTS.md`, skills, CI, or product code during reflection unless the user separately approves the proposal for implementation. Never promote secrets, customer data, raw production evidence, or private transcript content into committed artifacts.
