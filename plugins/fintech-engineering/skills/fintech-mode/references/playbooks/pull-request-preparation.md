# Pull-request preparation

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Resolve the repository's default branch from the authoritative host and choose it as the PR base unless the user or ticket explicitly names another target; record the source of any override.
2. Fetch the exact selected base, refresh or rebuild the candidate from it, and resolve conflicts deliberately. A local checkout, branch name, or earlier PR base does not select the target.
3. Compare the candidate commit set and complete diff with the selected base. Remove unrelated branch history instead of retargeting it into the pull request.
4. Confirm the worktree contains only the intended change and ordered, reviewable commits.
5. Run focused and proportionate broad verification.
6. Obtain the current synthetic-merge result through `$pre-push-review`; reuse an unchanged result under its invalidation rules. Branch-only success does not establish push readiness.
7. Invoke `$pre-push-review`, including the pre-edit adversarial proof gate, capability report, synthetic-merge result, and any contested or high-risk invariants in its scope.
8. Push and open or update the pull request only when requested; never infer merge or deploy authority.
9. Read the pull request back from the host and confirm its actual base, head branch, and exact head SHA before reporting or starting CI follow-through.
