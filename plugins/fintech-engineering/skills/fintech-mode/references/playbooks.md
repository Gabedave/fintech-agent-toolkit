# fintech engineering playbooks

Choose one primary playbook for the requested outcome. Add another only for a distinct requested outcome with its own steps; supporting skills do not imply additional playbooks. In particular, verifier updates inside a feature stay in the feature playbook, and defects fixed during pull-request check follow-through stay in the CI-failure playbook. Put the selected steps in the working plan verbatim enough that completion and explicit skips remain auditable.

Unless the user explicitly requests local-only work or withholds commit, push, or pull-request actions, pair every non-trivial production repository-editing playbook with pull-request preparation. Select `$ci-babysit` through the latest-head checks and review state unless the user withholds CI follow-through. A CI-only constraint leaves pull-request delivery intact; a withheld commit or push also blocks any downstream PR delivery that would require those unpublished commits. Never invent an empty or stale PR to preserve a downstream stage. Throwaway prototypes stay local unless the user separately asks to retain or publish them. This default delivery path does not add the CI-failure playbook unless a failure must be diagnosed or repaired, and never grants merge or deploy authority.

## None — proportional trivial task

Use no shared playbook when the task is a small mechanical edit with an obvious boundary and direct proof. Make the requested scoped change, run the closest direct check, review the diff, and stop at the user's authorization boundary. Do not invoke `fintech-mode` or supporting skills merely to manufacture process.

## Investigation

1. Define the observable question and evidence that would answer it.
2. Run `$how` to trace the current runtime path, data shapes, callers, configuration, tests, and operational boundary.
3. Run `$why` when historical intent is material.
4. Test competing explanations with the smallest read-only check that can distinguish them.
5. Report facts, inference, unknowns, and searches with no evidence.
6. Stop after the evidence-backed answer unless the user separately authorizes a change.

## Bug fix

1. Capture the exact symptom, environment, input, and first bad boundary.
2. Reproduce the defect through the same surface where practical.
3. Use `$how`; add `$why` only when historical intent affects the expected behaviour.
4. Form competing falsifiable hypotheses and run the smallest experiment that distinguishes them.
5. Confirm the root mechanism before editing.
6. Add or retain a regression check that detects the original defect when practical.
7. Change the smallest root mechanism and verify the original reproduction plus adjacent success and failure behaviour.

## Feature

1. Identify the user-visible outcome, public seam, compatibility constraints, and named domain data shape.
2. Run `$how`, then `$architect` when the routing contract identifies an architectural boundary.
3. Check ownership, independent workstreams, shared mutable state, and the smallest safe decomposition before implementation.
4. Settle observable uncertainty with a bounded throwaway prototype when cheaper than speculation.
5. Deliver one thin end-to-end behaviour path.
6. Cover contracts, compatibility, negative paths, retries, and recovery before adding breadth.
7. Run the repository verifier and maintain its map when the proof boundary changed.

## Refactor

1. Run `$how` and pin current behaviour with existing or characterization evidence.
2. Name the missing or incorrect domain boundary and the desired caller-facing shape.
3. Run `$architect` for a substantial boundary change and prefer subtraction over parallel abstractions.
4. Change one structural boundary at a time while keeping behaviour evidence green.
5. Migrate callers and remove superseded APIs; do not leave an indefinite dual path.
6. Prove behaviour equivalence and explain the reader-load improvement.
7. Do not mix intended behaviour changes into the refactor silently.

## Performance

1. Define the metric, workload, environment, variance, and finish threshold.
2. Capture and retain a repeatable baseline trace or profile.
3. List measured hypotheses and choose the riskiest unknown first.
4. Change one cause, rerun the identical workload, and compare parsed evidence rather than impressions.
5. Keep or revert each attempt explicitly and record why.
6. Recheck correctness, resource ceilings, and adjacent workloads after improvement.
7. Faster-looking code without comparable measurements is unverified.

## Prototype

1. State the observable question and the smallest experiment that can answer it.
2. Isolate the prototype from production paths, credentials, customer data, and shared environments.
3. Define the success or discard threshold before running it.
4. Record the result and remove throwaway artifacts.
5. If retained, redesign and verify the result as production code rather than promoting the experiment unchanged.

## Verification maintenance

1. Run `$maintain-verification` against every feature in the affected repository verifier.
2. Compare mapped entry points and proof claims with current source and tests.
3. Run the verifier doctor/plan surface and one safe live or automated pass per feature where available.
4. Classify each feature as clean, changed, or blocked; distinguish product regressions from verifier defects and environment failures.
5. Change only verifier-owned assets during a verifier-maintenance task unless product changes were separately authorized.

## Long-running or handoff work

1. Use `$work-continuity` to define a checkable finish predicate and compact resume state.
2. Work in the smallest justified iteration: hypothesis, change or observation, verification, keep or discard.
3. Record consequential decisions and failed directions without copying raw transcripts or sensitive evidence.
4. Refresh the resume state at material boundaries and before pausing.

## CI failure

1. Confirm the failing check belongs to the latest commit.
2. Reproduce the exact command locally when practical.
3. Classify product failure, test defect, infrastructure, configuration, superseded result, or flake from evidence.
4. Fix only when authorized and run `$pre-push-review` before an authorized push.
5. Use `$ci-babysit` to follow new runs and review threads.

## Pull-request preparation

1. Resolve the repository's default branch from the authoritative host and choose it as the PR base unless the user or ticket explicitly names another target; record the source of any override.
2. Fetch the exact selected base, refresh or rebuild the candidate from it, and resolve conflicts deliberately. A local checkout, branch name, or earlier PR base does not select the target.
3. Compare the candidate commit set and complete diff with the selected base. Remove unrelated branch history instead of retargeting it into the pull request.
4. Confirm the worktree contains only the intended change and ordered, reviewable commits.
5. Run focused and proportionate broad verification.
6. Refresh the selected base and run a disposable synthetic-merge check with the repository's lightweight doctor, contract, or build verifier. Branch-only success does not establish push readiness.
7. Invoke `$pre-push-review`, including the pre-edit adversarial proof gate, capability report, synthetic-merge result, and any contested or high-risk invariants in its scope.
8. Push and open or update the pull request only when requested; never infer merge or deploy authority.
9. Read the pull request back from the host and confirm its actual base, head branch, and exact head SHA before reporting or starting CI follow-through.
