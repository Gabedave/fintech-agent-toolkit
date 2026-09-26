# Implementation readiness contract

Apply this contract before production edits for every non-trivial implementation. It moves proof and
environment discovery ahead of the change instead of leaving them for review or CI.

## Risk classification

Classify the change as `high`, `standard`, or `not-applicable` before editing. Authentication,
authorization, money movement, schemas, migrations, shared mutable state, concurrency, destructive
operations, and release infrastructure are high risk. When discovery is incomplete, record
`assess-before-edit` and finish the assessment before changing production code.

## High-risk proof gate

For high-risk work, put this table in the working plan and complete it before production edits:

| Scenario class | Invariant | Executable evidence before editing |
| --- | --- | --- |
| definitive rejection | A terminal negative result cannot partially commit or reopen ownership. | Named failing test or deterministic reproduction |
| ambiguous outcome | A timeout, response loss, or unknown provider result cannot authorize unsafe retry. | Named failing test or deterministic reproduction |
| replay/idempotency | Repeating the same command or event cannot duplicate its durable effect. | Named failing test or deterministic reproduction |
| concurrent ownership | Competing workers or requests cannot both acquire authority. | Named failing test, race fixture, or database-backed reproduction |
| state/identity fencing | Stale state, tenant, attempt, amount, currency, or provider identity cannot finalize another operation. | Named failing test or deterministic reproduction |

The evidence must fail for the absent or incorrect behaviour, not because the local environment is
unavailable. If a class truly cannot apply, redesign the classification or document the disqualifying
domain evidence; do not silently omit it. Independent review checks this completed gate but does not
serve as its first author.

## Capability preflight

Before expensive verification, run the selected repository verifier's declared capability profile.
Use the profile that matches the intended command rather than treating one missing capability as a
blocker for every test level. Record `ready` and `blocked` classifications without raw host or provider
details. A blocked capability is incomplete local evidence and never waives required CI.

If a repository repeatedly depends on an undeclared capability, repair its verifier through
`$maintain-verification`; do not encode product-specific runtimes or commands in this shared plugin.

## Synthetic merge readiness

Before an authorized push, refresh the selected base and verify the combined base-plus-head tree. Use
the plugin's `scripts/verify_merge_candidate.py` with the repository's lightweight doctor, contract,
or build check. The command executes in a disposable worktree and returns a machine-readable result.

A conflict, missing ref, missing verification command, or failing combined-tree check blocks push
readiness. Branch-only success cannot substitute for this result. Run product tests in the repository's
normal verifier; the generic merge command must not install dependencies, weaken checks, or publish
the temporary worktree.
