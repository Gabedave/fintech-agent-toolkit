# Operating model

A repository opts in through its root `AGENTS.md`. Engineers describe the desired outcome; `fintech-mode` selects a proportionate playbook and supporting skills.

1. Establish the user-visible outcome, affected repository, local instructions, and authorized actions.
2. Trace current behavior with `how`. Add `why` for relevant history, `blast-radius` for uncertain ownership, and `architect` for high-impact boundaries.
3. Implement in small, verifiable slices using repository-owned tests and feature maps. Use `maintain-verification` when that proof is stale or missing.
4. Record consequential decisions and resume state when work spans sessions or teams.
5. Apply `pre-push-review` to a candidate-final implementation. For an authorized pull request, `ci-babysit` follows the exact latest revision and review state.
6. Use `reflect` when repeated friction supports a durable improvement.

For non-trivial implementation, the toolkit defaults to reviewed PR delivery and CI follow-through. The user or adopting repository may narrow that path, including local-only work. A requested diagnosis remains read-only. Merge, deployment, production mutation, ticket updates, and team messages require their own authorization. A green check is evidence for review, not permission to merge.

## Fintech proof boundaries

Apply extra scrutiny to authentication, identity, ledger and balance state, money movement, provider outcomes, privacy, migrations, concurrency, retries, idempotency, and recovery. Use isolated test services and fake providers for active verification. Read-only production observability requires the adopting organization's own policy.

## Decision records

The [decision-record policy](../plugins/fintech-engineering/skills/architect/references/decision-records.md) separates task rationale, local execution trails, and lasting repository ADRs. Keep actual ADRs in the owning repository. Do not publish private notes as a side effect of committing code.
