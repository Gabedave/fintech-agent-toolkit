# Review protocol

## Severity

- **Critical:** exploitable, destructive, or fundamentally unsafe.
- **Major:** likely functional failure, serious regression, broken contract, or missing essential coverage.
- **Minor:** worthwhile improvement that does not block team review.

Do not invent findings. Style preference is not a blocker unless it creates a concrete correctness, security, compatibility, operational, or maintenance risk.

## Evidence

Review correctness, invalid states, security boundaries, transactions, retries, timeouts, idempotency, partial failure, cleanup, resource use, contracts, migrations, dependencies, test quality, accessibility, privacy, observability, and maintainability where applicable.

For contested or high-risk design, also review the caller-facing data shape, alternatives considered, compatibility and rollback, ownership of mutable state, verification seam, and any implementation evidence that should have invalidated the selected design. Use this existing gate instead of creating a separate `interrogate` step.

For every acceptance criterion retain:

`requirement -> changed seam -> focused evidence -> broad evidence -> status`

Use `confirmed`, `partial`, `unverified`, or `failed`. A prior run, stale reviewer verdict, or successful check that did not exercise the changed behavior is not fresh evidence.

### Changed-boundary proof

Derive relevant risks from the requirements and source before choosing tests. Repository maps are an execution index, not the ceiling of the review. Reuse their commands, but inspect whether the selected cases actually cross the changed boundary. A test file being mapped or a large passing test count does not establish that.

For critical stateful or provider-facing changes, extend the existing evidence chain with a compact account of the real producer/data format, state changed by each step, the next consumer, and which collaborators are real or doubled. Follow writes through to the subsequent read, retry, rescan, or cleanup: refreshing one entity does not refresh another snapshot, and a return value does not prove a collaborator had no side effects.

Choose the concrete failure combinations relevant to that change, not a mandatory Cartesian product. Examples include partial success before an exception, a missing child record, an actual adapter's wrapped error, late evidence after repair, and maintenance while delivery is paused. Derive fixture shapes from their real writer/adapter, not just the reader being tested. Preserve nearby success and no-side-effect controls.

Use the smallest check that retains the mechanism: a real state-changing collaborator, adapter, storage query, controlled interleaving, or the exact full test command for an order-dependent failure. A success stub that removes the central mutation or dependency behavior cannot confirm that criterion. Run the regression against the bad baseline when safe; otherwise state the sensitivity limitation. Ensure assertions observe the dependency actually used, not an unused mock.

Missing essential proof of the main acceptance behavior is blocking, not a non-blocking residual risk: use `NOT READY FOR TEAM REVIEW` for a demonstrated gap and `REVIEW INCOMPLETE` when the required investigation or environment is unavailable. Do not demand live providers, broad stress tests, or an extra reviewer when a bounded local check proves the risk. Mechanical changes retain their proportionate direct check.

## Review record

Keep the result compact, but always retain:

- review scope plus candidate and final snapshot identities;
- risk level and rationale, plus the high-risk invariant audit when required;
- `requirement -> changed seam -> focused evidence -> broad evidence -> status` for every criterion;
- remediation and reconciliation disposition for every Critical or Major finding;
- fresh verification, including checks that were blocked or unavailable;
- external evidence with sources and versions, or `not required`;
- remaining findings, assumptions, and unverified risks;
- the ADR assessment, reviewer-attempt count, and behavior-changing repair-cycle count.

Keep confirmed and not-applicable items to one concise row or sentence each. Expand failed, partial, or unverified evidence and every blocker. Low- and medium-risk reviews may combine common fields into a concise record. High-risk reviews and reviews that repaired a blocker must show the invariant and reconciliation entries explicitly. During reconciliation, restate only changed evidence and dispositions plus the current snapshot identity; do not repeat unchanged record fields.

Report `INDEPENDENT REVIEW: PERFORMED` only for a context-isolated reviewer; otherwise report `INDEPENDENT REVIEW: NOT PERFORMED`. The current context-isolated reviewer counts as an attempt even when it must not delegate a replacement reviewer. On an initial pass, report `CONSENSUS: ACHIEVED` only for a ready candidate without unresolved blockers, `CONSENSUS: NOT ACHIEVED` for a blocking or incomplete result, and `CONSENSUS: HUMAN DECISION REQUIRED` only for an actual product-intent or risk-tolerance dispute. End with exactly one of `STATUS: READY FOR TEAM REVIEW`, `STATUS: NOT READY FOR TEAM REVIEW`, or `STATUS: REVIEW INCOMPLETE`.

For toolkit plugin-behavior changes, completion evidence must include a live installed-candidate run from disposable Codex state. It must identify the clean candidate commit and manifest version and pass every checked-in behavior scenario. Deterministic routing and schema checks cannot substitute for this gate.

Review-gate/evaluator changes additionally use the local paired review-quality pilot. Routing-smoke success proves workflow decisions, not defect detection. The pilot must reproduce the seeded defects and accept their fixed controls; missing, failed, or incomplete cases are not a passing pilot. Keep product regressions in their owning repositories and synthetic evaluation fixtures in the toolkit.

## Stopping rules

Use one independent reviewer by default and at most one replacement if the first attempt fails operationally. Allow at most two behavior-changing repair-and-review cycles. Escalate a product-intent or risk-tolerance disagreement to a human instead of forcing consensus.
