---
name: ci-babysit
description: Follow a fintech pull request's latest commit through repository CI and review feedback, diagnose failures, and make authorized fixes until it is merge-ready. Use when authorized delivery includes CI follow-through or when the user asks to monitor, investigate, or repair PR checks; never infer permission to merge.
---

# Ci Babysit

Drive the current pull-request revision to an honest merge-ready status. A completed earlier run is stale after the head commit changes. Declare the operating mode: `check` for one status pass, `drive` for authorized repair and follow-through, or `monitor` for waiting on state changes without modifying the pull request.

## Establish identity

1. Resolve the repository, pull request, actual base branch, head branch, and exact head SHA from the repository host.
2. Independently resolve the repository's default branch. Require the PR base to match it unless the user or ticket explicitly selected another target; a branch name, local checkout, or older PR is not evidence of an override. Treat an unexplained mismatch as a blocker before following checks.
3. Read applicable repository instructions and the linked ticket.
4. Check conflicts, draft state, required checks, review state, and unresolved threads before waiting on jobs. Resolve review and conflict blockers before spending time on superseded CI where practical.
5. Treat requested changes and required checks as blockers; treat optional or superseded checks explicitly. Confirm the required aggregate gate and its expected inputs at the exact current head; green shards alone are insufficient. Required skipped, pending, unavailable, failing or stale results keep readiness unresolved.
6. Confirm there is one active babysitter for the pull request or coordinate ownership; do not create competing repair loops.

## Follow checks

In `check` or `monitor` mode, report authoritative state and stop at that scope. Investigate logs/source or reproduce failures only when diagnosis is requested; repairs require `drive` authorization.

- Prefer compact status polling that wakes on a state change rather than rapid repeated queries.
- After every push, read the PR again and replace the tracked SHA. Accept check and review results only when they belong to that exact latest head; older green or failing runs are superseded evidence.
- Inspect the failing step and its surrounding log, not only the job conclusion.
- Reproduce the exact command locally when practical.
- Classify each failure using [references/failure-states.md](references/failure-states.md).
- Distinguish a stale base or merge conflict from a defect in the head commit before rewriting product code.
- Treat automated review comments skeptically: reproduce concrete correctness claims and dismiss neither bots nor humans by identity alone.
- Do not label a failure flaky solely because a retry passed. Look for repeated historical evidence or a nondeterministic mechanism.
- Rerun only when the failure is demonstrably external, transient, or a known flake and rerunning is authorized by the task.

## Report meaningful changes

Keep polling and user-visible reporting separate. Compare the current PR head, check outcomes,
review blockers, and next action with the last reported state; polling itself is not a milestone.
Give concise updates for new evidence, a failure or required human action, a head change, or completion.
Group related results rather than repeating the full check inventory on each poll.

Continue verification while the state is unchanged. Respect higher-priority communication cadence
and explicit user requests; a necessary waiting check-in is one brief line without the unchanged inventory.
Finish with one consolidated account of what passed, what remains unresolved, and the human action needed.
These reporting rules do not change check requirements, exact-head tracking, or CI follow-through.

## Repair when authorized

If the user asked to fix the pull request, change the smallest root cause in the PR's isolated worktree, run focused verification, apply `$pre-push-review`, push, and then follow the new head SHA. Do not modify unrelated PRs or worktrees.

## Completion

For authorized PR delivery, make completed draft work ready for review and read back that state when all material evidence is confirmed. Retain draft only for an explicit user request or a named genuine blocker, with the next action recorded. A check-only or read-only request does not authorize changing draft state.

Report merge-ready only when the latest SHA has no known blocking review thread, conflict, or required-check failure and every required aggregate/input is confirmed. A missing aggregate or unintegrated product check is an explicit integration limit. List skipped, neutral, pending, and unavailable evidence separately. Never merge, deploy, dismiss review, or weaken branch protection without explicit authorization.
