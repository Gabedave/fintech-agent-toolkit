# CI failure

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Confirm the failing check belongs to the latest commit.
2. Reproduce the exact command locally when practical.
3. Classify product failure, test defect, infrastructure, configuration, superseded result, or flake from evidence.
4. Fix only when authorized and run `$pre-push-review` before an authorized push.
5. Use `$ci-babysit` to follow new runs and review threads.
