# Fintech engineering principles

Apply only the principles relevant to the task, but make the selection explicit for non-trivial work.

1. **Model the domain before coding.** Name the important entities, states, ownership, transitions, and invalid combinations before choosing implementation shapes.
2. **Protect boundaries and contracts.** Validate data where authority changes and trace producers and consumers before changing a public seam.
3. **Make retries safe.** Money movement, jobs, migrations, webhooks, and external-provider operations need explicit identity, ownership, idempotency, and recovery behaviour.
4. **Prove the real behaviour.** Prefer the real command, runtime, migration, storage, browser, device, or trace surface that exercises the risk.
5. **Fix the mechanism.** Reproduce, distinguish competing hypotheses, and repair the root cause instead of accumulating symptom patches.
6. **Work in verifiable units.** Each slice should have a clear outcome, exclusive write surface, and nearby proof.
7. **Minimise reader load.** Prefer explicit domain shapes, narrow interfaces, local reasoning, and deletion of superseded paths.
8. **Subtract before adding.** Reuse or simplify an existing boundary before creating another abstraction, configuration layer, or workflow.
9. **Separate concurrent writers.** Use independent worktrees and owners; serialize shared contracts, schemas, lockfiles, generated output, and mutable environments.
10. **Encode lessons in structure.** Repeated or severe failures should become tests, types, scripts, schemas, checks, or maintained skills rather than folklore.
11. **Preserve consequential rationale.** Record lasting choices, rejected alternatives, evidence, and reconsideration conditions where the owning team can find them. Use [the decision-record policy](../../architect/references/decision-records.md); do not confuse a task log with a permanent architectural decision.

Small mechanical changes may use a lighter path. Proportionality is not permission to skip the proof that directly covers the changed behaviour.
