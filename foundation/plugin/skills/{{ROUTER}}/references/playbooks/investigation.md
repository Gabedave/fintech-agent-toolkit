# Investigation

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Define the observable question and evidence that would answer it.
2. For a status-only question, read authoritative subject/revision and check/run state directly, using `$ci-babysit` check/monitor mode for a PR. Use `$how` when the question requires a source/runtime explanation or diagnosis; trace only that boundary.
3. Run `$why` when historical intent is material.
4. Test competing explanations with the smallest read-only check that can distinguish them.
5. Report facts, inference, unknowns, and searches with no evidence.
6. Stop after the evidence-backed answer unless the user separately authorizes a change.
