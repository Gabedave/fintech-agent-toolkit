---
name: pre-push-review
description: Review, repair, and verify local {{AUDIENCE}} changes before they are pushed for team review. Use automatically as the final quality gate after code, tests, migrations, configuration, or infrastructure change; do not use for read-only tasks unless explicitly requested.
---

# Pre Push Review

Perform the final evidence-backed quality gate without claiming software is defect-free.

## Scope and snapshot

1. Read applicable repository instructions and recover the independently fixed acceptance criteria.
2. Inspect the complete intended diff, including untracked files, against the correct merge base.
3. Exclude unrelated user work and record the candidate commit or diff identity.
4. When a pull request is requested, independently resolve the repository default and selected PR base, then inspect the candidate commit set and complete diff against that base. Require an explicit user or ticket source for a non-default target; unexplained branch-only commits block readiness.
5. Classify risk as low, medium, or high. Authentication, authorization, money movement, schemas, migrations, concurrency, destructive operations, and infrastructure are high risk.
6. For high risk, read and complete [the high-risk audit](references/high-risk-audit.md) before judging readiness. Reuse the pre-edit implementation-readiness evidence; do not create a competing checklist or substitute review-time prose for missing pre-edit proof.
7. When a design was contested or crossed a high-risk boundary, inspect its caller-facing model, considered alternatives, rejected directions, compatibility plan, and invalidation signals. This skill is the {{AUDIENCE}} replacement for a separate adversarial-review workflow.
8. For high-risk implementation, require the completed pre-edit readiness table: definitive rejection, ambiguous outcome, replay/idempotency, concurrent ownership, and state/identity fencing, each bound to named executable evidence. A table first assembled after implementation is a workflow finding even when the final behavior is correct.

## Verify and review

- Run focused checks that establish the candidate is coherent.
- Derive the review scope from requirements and actual producers/consumers before selecting mapped checks. Apply the changed-boundary proof rule in [the review protocol](references/review-protocol.md); passing nearby tests does not confirm a critical behavior they mock or omit.
- When an isolated reviewer is available and permitted, give one reviewer the requirements, repository instructions, stable diff, risk classification, and verification results without implementation conclusions. Keep the first pass read-only.
- Require every blocking finding to include location, failure scenario, severity, evidence, and remediation direction.
- Reproduce critical and major findings when practical. Challenge speculative findings with repository or authoritative evidence.
- Fix only in-scope blocking findings, rerun affected checks, and ask the same reviewer to reconsider disputed or repaired blockers.
- Reject unexplained parallel APIs, duplicated authority, unowned mutable state, proof weakened to match a regression, and implementation friction that invalidates the recorded architecture.
- Inspect the selected repository capability profile before expensive checks. A blocked or undeclared required capability remains incomplete evidence and cannot be relabeled as a product pass.
- For non-trivial implementations, apply [the decision-record policy](../architect/references/decision-records.md) to the actual diff. Report `ADR required: <path>` or `ADR skipped: <concrete reason>`. Check required records and any consequential trail against their evidence, ownership, current design, and review status. A required ADR missing from the candidate or an unresolved assessment blocks readiness. Routine fixes covered by an existing ADR need a link, not a duplicate record.

Always read [references/review-protocol.md](references/review-protocol.md) for severity, changed-boundary proof, reporting, and completion rules. Read [references/high-risk-audit.md](references/high-risk-audit.md) only for high-risk changes. Read [references/external-evidence.md](references/external-evidence.md) only when a material conclusion depends on current, version-specific, security-sensitive, standards-based, or locally unavailable facts.

## Final verification

Freeze the final diff and run the broadest checks proportionate to risk. Confirm no secret, customer data, generated noise, or unrelated file entered the change. Do not commit, push, open a pull request, merge, or deploy unless the user authorized that action.

For an authorized push, independently refresh the selected base and run the plugin's `scripts/verify_merge_candidate.py` with a repository-owned lightweight check. Accept readiness only when the disposable combined tree is conflict-free and the supplied check passes. Record the exact base and head SHAs; branch-only verification is stale evidence for this gate.

For a change to this toolkit's plugin behavior, deterministic validation is necessary but not sufficient. Install the exact clean candidate commit into disposable Codex state, run every model-backed behavior scenario through `scripts/release_smoke.py`, and retain the reported plugin version, commit, and pass count in the pull request. A missing, partial, version-mismatched, or failed live result is `NOT READY FOR TEAM REVIEW`.

When changing this review gate or its review-quality evaluator/fixtures, also run the bounded local pilot with `scripts/release_smoke.py --review-quality`. Report reproduced defects, accepted fixed controls, false blockers, and elapsed time. It supplements the existing gate; it is not another product reviewer or proof of general review accuracy.

Use the protocol's compact review record, expanding high-risk or repaired reviews rather than omitting their evidence. End with exactly one status: `STATUS: READY FOR TEAM REVIEW`, `STATUS: NOT READY FOR TEAM REVIEW`, or `STATUS: REVIEW INCOMPLETE`.
