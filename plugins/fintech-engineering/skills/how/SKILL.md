---
name: how
description: Explain how a fintech system, feature, or runtime path currently works using source, tests, configuration, and operational boundaries. Use automatically before non-trivial engineering changes and for architecture explanations; keep the investigation read-only.
---

# How

Build a trustworthy current-system model before proposing or reviewing a change. This skill explains what the system demonstrably does; use `$why` separately when historical intent matters.

## Trace the real path

1. Define the user, operator, job, API, or provider boundary being explained.
2. Start at the actual entry point and follow callers, data shapes, state transitions, persistence, configuration, external boundaries, and observable outcomes.
3. Read tests and repository verifier maps as claims to validate against source, not as substitutes for source inspection.
4. Trace important failure, retry, authorization, concurrency, and cleanup paths where they affect the explanation.
5. Use read-only runtime or observability evidence when static inspection cannot settle current behaviour and the workspace authorization allows it.

For a contained path, investigate directly. For a system spanning several independent areas, split read-only exploration by boundary when safe and reconcile it into one model; use a sequential fallback when parallel investigation is unavailable.

## Explain and critique

Read [references/explanation.md](references/explanation.md). Separate confirmed behaviour, inference, and unknowns. After the neutral explanation, identify concrete design pressure only when supported by evidence: unclear ownership, invalid states, duplicated paths, leaky boundaries, unsafe retries, missing proof, or high reader load.

Do not edit source, claim historical rationale, or turn a design preference into a defect during this skill. Return the model to `$fintech-mode` or `$architect` when the task continues into implementation or design.
