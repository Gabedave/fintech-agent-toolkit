# Implementation readiness contract

Apply this contract before production edits for every non-trivial implementation. It moves proof and
environment discovery ahead of the change instead of leaving them for review or CI.

## Risk classification

Classify the change as `high`, `standard`, or `not-applicable` before editing. Authentication,
authorization, money movement, schemas, migrations, shared mutable state, concurrency, destructive
operations, and release infrastructure are high risk. When discovery is incomplete, record
`assess-before-edit` and finish the assessment before changing production code.

## Resource lifecycle

Classify the proposed change's resource-lifecycle effect independently of correctness risk before
editing. Use `material-bound-required` when the changed lifecycle has a concrete material growth
exposure in per-operation work, retained state, lifetime, or fan-out as traffic, data, time, or
concurrency grows. This includes a fix intended to reduce existing growth: its new ceiling and
cleanup still need proof. Use `not-material` with a concrete reason when the changed lifecycle has no
material exposure; `assess-before-edit` when its effect or exposure is not yet known; and
`not-applicable` only when there is no implementation. A request mentioning a job, queue, retry, or
money boundary does not itself establish a growth exposure: an ownership-only retry change with no
resource effect established remains `assess-before-edit`, while fixing indefinite completed-job
retention requires a bound even when correctness risk is standard.

Separate open assessment questions from established obligations. When resource exposure is unresolved,
state what discovery must determine; do not present material-growth requirements as already applicable.
Establish those requirements only after evidence supports a material-growth classification.
Correctness risk does not determine resource exposure; finish the assessment before production edits.

For material growth, state the expected and peak workload; the per-operation or retained-state ceiling;
concurrency and replica effects; cleanup or expiry; safe behaviour at the ceiling; and the repository-owned
check plus aggregate production signal that will distinguish healthy operation from exhaustion. Make the
bound and safety invariant explicit before editing, and obtain proportionate executable evidence before
review. A durable ledger or recovery record may need to grow; bound each operation and plan capacity rather
than deleting financial truth. Do not invent universal numerical budgets or require a broad load test when
a deterministic check proves the risk. If no trustworthy ceiling or safe saturation behaviour exists,
record the exposure as unresolved instead of calling the implementation ready.

## High-risk proof gate

For high-risk work, put this table in the working plan and complete it before production edits:

| Scenario class | Invariant | Executable evidence before editing |
| --- | --- | --- |
| definitive rejection | A terminal negative result cannot partially commit or reopen ownership. | Named semantic regression or sensitive invariant control |
| ambiguous outcome | A timeout, response loss, or unknown provider result cannot authorize unsafe retry. | Named semantic regression or sensitive invariant control |
| replay/idempotency | Repeating the same command or event cannot duplicate its durable effect. | Named semantic regression or sensitive invariant control |
| concurrent ownership | Competing workers or requests cannot both acquire authority. | Named semantic regression, deterministic race fixture, or sensitive invariant control |
| state/identity fencing | Stale state, tenant, attempt, amount, currency, or provider identity cannot finalize another operation. | Named semantic regression or sensitive invariant control |

For new or defective behaviour, the evidence must fail for the absent or incorrect behaviour, not because the local environment is unavailable. For an unaffected invariant in a refactor, retain a passing pre-edit control and demonstrate that a controlled unsafe variant is detected; do not invent a baseline defect. If a class truly cannot apply, redesign the classification or document the disqualifying
domain evidence; do not silently omit it. Independent review checks this completed gate but does not
serve as its first author. Record command results and source/file identity before the first production write. A table reconstructed after implementation remains a missed pre-edit gate even when final tests pass; record its disposition without rewriting the chronology.

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
