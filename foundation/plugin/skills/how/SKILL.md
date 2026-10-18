---
name: how
description: Explain how a {{AUDIENCE}} system, feature, or runtime path currently works using source, tests, configuration, and operational boundaries. Use automatically before non-trivial engineering changes and for architecture explanations; keep the investigation read-only.
---

# How

Build a trustworthy current-system model before proposing or reviewing a change. This skill explains what the system demonstrably does; use `$why` separately when historical intent matters.

## Trace the real path

1. Define the user, operator, job, API, or provider boundary being explained.
2. Before making current-source claims, resolve the repository's default branch and authoritative base SHA from its host. Run the installed plugin's [snapshot helper](../../scripts/verify_repository_snapshot.py) with the local base ref and authoritative base SHA, then record the exact head, divergence, authority state, and dirty state.
3. Treat `attention` as a source-selection decision, not permission to repair the checkout. Prefer read-only host inspection or, when local writes are authorized, a disposable worktree at the authoritative revision. The preflight and this skill must not update or clean the user's checkout.
4. Start at the actual entry point and follow callers, data shapes, state transitions, persistence, configuration, external boundaries, and observable outcomes.
5. Read tests and repository verifier maps as claims to validate against source, not as substitutes for source inspection.
6. Trace important failure, retry, authorization, concurrency, and cleanup paths where they affect the explanation.
7. Use read-only runtime or observability evidence when static inspection cannot settle current behaviour and the workspace authorization allows it.

For a contained path, investigate directly. For a system spanning several independent areas, split read-only exploration by boundary when safe and reconcile it into one model; use a sequential fallback when parallel investigation is unavailable.

## Explain and critique

Read [references/explanation.md](references/explanation.md). Separate confirmed behaviour, inference, and unknowns. After the neutral explanation, identify concrete design pressure only when supported by evidence: unclear ownership, invalid states, duplicated paths, leaky boundaries, unsafe retries, missing proof, or high reader load.

Do not edit source, claim historical rationale, or turn a design preference into a defect during this skill. Return the model to `${{ROUTER}}` or `$architect` when the task continues into implementation or design.
