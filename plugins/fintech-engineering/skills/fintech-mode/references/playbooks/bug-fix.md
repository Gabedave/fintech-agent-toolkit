# Bug fix

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Capture the exact symptom, environment, input, and first bad boundary.
2. Reproduce the defect through the same surface where practical.
3. Use `$how`; add `$why` only when historical intent affects the expected behaviour.
4. Form competing falsifiable hypotheses and run the smallest experiment that distinguishes them.
5. Confirm the root mechanism before editing.
6. Add or retain a regression check that detects the original defect when practical.
7. Change the smallest root mechanism and verify the original reproduction plus adjacent success and failure behaviour.
