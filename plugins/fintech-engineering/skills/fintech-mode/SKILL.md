---
name: fintech-mode
description: Route any task in a fintech product repository through the proportionate default engineering workflow, including choosing the no-playbook path for a small mechanical edit. Use without waiting for the user to name supporting skills; do not use for unrelated general questions.
---

# Fintech Mode

Turn the user's requested outcome into a proportionate engineering loop while preserving the authorization boundary. Use this skill as the default router for fintech repository work; for a small mechanical edit, route to playbook `none` and stop before loading supporting workflow skills. The user should not need to name `how`, `why`, architecture, verification maintenance, work continuity, pull-request preparation, or CI follow-through to receive their benefits. A request to diagnose does not authorize a fix, and no request to prepare or follow a pull request authorizes merging or deploying it.

## Ground the task

Before selecting probes, interpreting verification or runtime evidence, or making a material evidence claim, read [operation and claim scope](references/acceptance-and-evidence.md#operation-and-claim-scope). This applies to read-only investigation, review and status work as well as implementation.

1. Read every applicable `AGENTS.md` from the workspace root through the affected working directory.
2. Inspect the selected ticket, linked pull requests, repository state, manifests, and existing checks.
3. When work concerns an existing pull request or may create or update one, resolve the repository's default branch from its authoritative host before choosing or checking the PR base. Use that default unless the user or ticket explicitly names another target. A current checkout, local branch name, linked PR, or previously reviewed base is context, not authority. Record the resolved default and any explicit override in the plan.
4. For non-trivial implementation, diagnosis, review of code behavior, or system explanation, use `$how` and retain its source-provenance result and revision. For status-only checks or monitoring, read authoritative check/run state directly; use `$ci-babysit` in `check` or `monitor` mode for PRs. Identify the exact subject/revision and evidence limits. Load `$how` only when explaining a cause or interpreting source/runtime behavior; status alone does not authorize diagnosis or repair.
5. Use `$why` automatically when historical intent, an unusual constraint, or the reason for an existing design could change the correct decision.
6. Use `$blast-radius` automatically when ownership, contracts, consumers, data, release boundaries, or affected repositories actually need mapping. An unknown CI failure alone calls for diagnosis; select this additional skill when that diagnosis reveals a mapping question.
7. State the observable outcome, compatibility requirements, highest-risk failure mode, and evidence required for completion.
8. In the first working plan, record one authorization ledger for `edit`, `commit`, `push`, `open-pull-request`, `merge`, `deploy`, and `user-installation` at minimum, plus relevant ticket/team actions. Apply [the company delivery policy](references/playbooks.md#delivery-and-authorization) within the user's task/session scope. Reuse this ledger; subsequent plans and the final handoff reference it and report only changed permissions, relevant withheld actions, and blockers. Keep all classifications inspectable, including installation and withheld merge/deploy; an explicitly required structured report still includes every required field. Review, diagnosis, explanation, and status requests remain read-only. Recording an action never grants it.
9. Preserve unrelated work. Use a separate branch and worktree, created from the selected PR base, for each affected product repository.

Before applicable pre-edit proof tests or production edits, read [acceptance and evidence](references/acceptance-and-evidence.md) and fix the completion criteria independently. Before production edits, apply [the implementation readiness contract](references/implementation-readiness.md). Classify risk and resource growth independently, complete the adversarial proof gate for high-risk work, and record the selected repository capability profile. When either classification is still uncertain, finish discovery before editing instead of deferring the decision to review.

For read-only work, implementation-readiness fields are `not-applicable`, including resource lifecycle. Existing-PR identity and lifecycle checks remain applicable independently of edit permission.

When the task already names an existing pull request, continue that PR. Do not classify `open-pull-request` as authorized or create a duplicate unless the user explicitly asks for another PR.

For a new delivery task, distinguish an existing PR that was actually resolved from a possible future PR. Select the authorized update path only for an existing PR; otherwise use the authorized new-PR path. Label a stage whose prerequisites are not established as conditional or withheld, rather than claiming it is available now.

For any existing or planned pull request, keep merge authorization as an explicit lifecycle boundary even when the user withholds or prohibits merge. An inactive merge execution step does not make that authorization boundary inapplicable.

## Choose a playbook

Read the [playbook index and delivery policy](references/playbooks.md), then only the selected playbook. Consult [principles](references/principles.md) when deciding a design/proof trade-off and [routing data](references/routing-contract.json) when validating routing. Select the narrowest matching playbook and retain its steps in the working plan. Keep every selected step visible until completion; if a step does not apply, mark it skipped with a concrete reason instead of silently dropping it.

Apply these routing distinctions before selecting supporting skills:

- A spelling correction, formatting-only change, generated-file cleanup, or similarly bounded mechanical edit uses playbook `none` and no shared workflow skills. Run only the closest direct check. Auditing or repairing verifier-owned assets or a proof boundary is not this path, even when the edit is only a moved test path; when that repair is the requested outcome, use the verification-maintenance playbook.
- A status-only request uses investigation, with `$ci-babysit` in `check` or `monitor` mode for an existing PR. Its small scope does not make it a mechanical edit; retain direct host reads and load source-explanation skills only if diagnosis becomes authorized.
- The primary playbook describes the user's requested outcome. Add another playbook only for a separate requested outcome with its own steps; selecting a supporting skill never adds its namesake playbook by itself.
- A feature that changes a verifier or proof boundary may select `$maintain-verification`, but it does not add the verification-maintenance playbook unless auditing or repairing verification is itself a requested outcome.
- A public contract change across repositories changes the proof boundary: select `$maintain-verification` to reconcile the affected repository maps, while keeping the feature playbook primary.
- Pull-request check diagnosis and repair uses the CI-failure playbook. A defect fixed within that flow is a CI-failure step, not an additional bug-fix playbook. Add the long-running playbook only when the requested follow-through spans sessions or has a persistent finish condition.
- Non-trivial production implementation work keeps its implementation playbook primary. Add pull-request preparation and `$ci-babysit` when the company default and user authorize publication and follow-through. A throwaway prototype stays local and unpublished unless the user separately asks to retain or publish it; once promoted to production implementation, the default delivery path applies. Do not add the CI-failure playbook until diagnosing or repairing a failure is actually part of the work.

Use `$architect` before implementation when the task changes a public contract, domain model, schema, shared state, authentication or money boundary, cross-repository seam, or substantial structural boundary. For observable product or technical uncertainty, prefer a bounded throwaway experiment over asking the user to speculate; do not retain prototype code unless it satisfies the production design and verification bar.

Use `$work-continuity` when work spans sessions or repositories, has a long-running finish predicate, needs a team handoff, or has accumulated several material decisions. Keep diagnosis read-only unless the user also authorized changes. Do not apply this full workflow to a trivial documentation or mechanical edit.

For non-trivial changes, read [the shared decision-record policy](../architect/references/decision-records.md). Keep routine rationale, an execution trail, and a permanent repository ADR distinct. Assess ADR need during design, after a consequential pivot, and at final review; this assessment alone does not select `$architect` or `$work-continuity`. Read-only work does not authorize record writes.

## Execute in verifiable slices

- Demonstrate a defect before changing its cause when practical.
- Implement the smallest coherent slice through a stable public seam.
- After each behavior-changing slice, run the closest reliable check.
- Discover and use `$REPO_ROOT/.agents/skills/verify-*` for application-specific verification.
- For a user-facing UI change or publication of UI evidence, read [the UI evidence contract](references/ui-verification.md) before selecting checks or uploading captures. Carry its completed record into the pull request and final handoff.
- Select a repository verifier only when its mapped application evidence directly covers the requested question or change. Repository presence alone is insufficient; a historical or process explanation does not select an application verifier unless current runtime behaviour must also be proved.
- Use `$maintain-verification` when a critical feature is unmapped, a verifier command or proof boundary changed, or source evidence suggests the verifier is stale.
- Keep deterministic commands in repository scripts so humans, skills, and CI use the same path.
- Treat flaky, skipped, or unavailable checks as unresolved evidence, not as passing results.
- After repeated failed hypotheses or design friction, stop patching and revisit the current-system model, assumptions, and architecture.
- Run repository-declared capability preflight before expensive verification. Select capabilities by verification profile; never treat a blocked profile as passing or as a waiver for exact-head CI.

## Finish

1. Map every acceptance criterion to fresh evidence.
2. Use `$pre-push-review` after implementation reaches candidate-final state. It is the sole independent review escalation: route contested or high-risk design concerns into its review scope instead of invoking a separate adversarial-review skill.
   Include `ADR required: <path>` or `ADR skipped: <concrete reason>` in the review and final handoff for non-trivial implementations. Link any necessary trail; do not publish local notes implicitly.
3. For implementation delivery, keep the pull-request description concise and include the ticket when one exists, customer or product impact, verification, and related cross-repository pull requests. For platform, CI, workflow, agent, or tooling changes, also state the operational capability now, what is not implemented, required activation or configuration, and the next integration step.
4. Before an authorized push, require the current synthetic merge result owned by `$pre-push-review`; follow [its reuse and invalidation rules](../pre-push-review/SKILL.md#final-verification). A conflict or failing combined-tree check blocks readiness even when branch-only tests pass.
5. After creating or updating a pull request, read it back from the repository host and confirm its actual base branch and exact head SHA. A mismatch with the resolved default or explicit target is a blocker; rebuild the candidate from the correct base rather than carrying unrelated commits across branches.
6. Verify installed plugin bytes/version separately from canonical source when toolkit identity affects a claim; a new task must load the selected version. A source update does not update an active installation.
7. Report confirmed, partial, unverified, and failed evidence honestly. Green CI means merge-ready for a human decision; it is not permission to merge.
