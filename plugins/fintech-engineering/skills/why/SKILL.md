---
name: why
description: Reconstruct why fintech code or process has its current shape using Git history, pull requests, tickets, documentation, and available observability evidence. Use automatically when historical intent could change a non-trivial engineering decision; do not infer intent from code alone.
---

# Why

Answer historical-intent questions with traceable evidence. Keep the investigation read-only.

## Investigate

1. Define the decision or behavior whose origin is in question.
2. Trace the current runtime behavior enough to identify the owning lines, contract, and callers.
3. Inspect `git log`, `git blame`, and the introducing or materially changing commits.
4. Follow linked pull requests and issue-tracker records. Search available design documents and team records only when relevant and authorized.
5. Use privacy-safe aggregate observability evidence when it explains an operational constraint; never reproduce raw customer or provider data.
6. Record empty searches so missing evidence is explicit.

Read [references/evidence.md](references/evidence.md) for source precedence and reporting rules.

## Report

Separate:

- **Current behavior:** what the system demonstrably does now.
- **Historical facts:** dated decisions supported by direct sources.
- **Inference:** the most likely rationale and why it follows from the facts.
- **Unknowns:** questions no available source answers.

Link or name the exact commits, pull requests, tickets, and documents used. Never invent a plausible rationale to fill an evidence gap.
