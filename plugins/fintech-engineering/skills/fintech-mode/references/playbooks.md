# fintech engineering playbooks

Choose one primary playbook for the requested outcome. Add another only for a distinct requested outcome with its own steps; supporting skills do not imply additional playbooks. In particular, verifier updates inside a feature stay in the feature playbook, and defects fixed during pull-request check follow-through stay in the CI-failure playbook. Keep selected steps and justified skips inspectable in one working plan; later updates report changes.

## Delivery and authorization

Apply the company delivery policy before selecting delivery stages. Default delivery: pull-request. For non-trivial implementation in repositories adopting this default, requested delivery includes edit, commit, push, update an existing or open a new pull request, and CI follow-through unless the user or repository narrows those stages. Respect local-only, no-commit, no-push, no-PR, no-CI, read-only, and requested-draft restrictions. Make ready work reviewable. Merge, deployment, ticket updates, and team messages require separate explicit authorization. Personal or user-wide active plugin/skill installation changes are a separate authority boundary; classify those actions when relevant and perform them only within applicable explicit task/session authorization. Preserve every required authority class, including installation, in the canonical authorization ledger; reference it in the final decision and report changes and relevant withheld actions. Required structured outputs retain every required field. Reading installed instructions is a read action, not an installation change; honor any explicit read restriction. Honor authorization already granted within its scope, without asking again or extending it. Authorized product-repository work and owned disposable fixture setup retain their existing task scope. Readiness and green CI never grant merge or deployment authority.

Pair a non-trivial production repository-editing playbook with pull-request preparation and select `$ci-babysit` only when the company policy and user authorize publication and follow-through. A CI-only restriction leaves otherwise authorized pull-request delivery intact; a withheld commit or push also blocks downstream PR delivery that would require those unpublished commits. Never invent an empty or stale PR to preserve a downstream stage. Throwaway prototypes stay local unless the user separately asks to retain or publish them. Selecting delivery stages does not add the CI-failure playbook unless a failure must be diagnosed or repaired, and never grants merge or deploy authority.

Assess pull-request lifecycle applicability separately from general action permissions. When no pull request exists or is planned and the requested outcome has no pull-request delivery lifecycle, there is no such lifecycle to report; general merge/deployment prohibitions still apply. An existing or planned pull request retains the router's merge-authorization boundary even when execution is withheld.

## Select one workflow

Read only the selected workflow; add another only for a distinct requested outcome.

- [None — proportional trivial task](playbooks/none.md)
- [Investigation](playbooks/investigation.md)
- [Bug fix](playbooks/bug-fix.md)
- [Feature](playbooks/feature.md)
- [Refactor](playbooks/refactor.md)
- [Performance](playbooks/performance.md)
- [Prototype](playbooks/prototype.md)
- [Verification maintenance](playbooks/verification-maintenance.md)
- [Long-running or handoff work](playbooks/long-running.md)
- [CI failure](playbooks/ci-failure.md)
- [Pull-request preparation](playbooks/pull-request-preparation.md)
