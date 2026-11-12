# Refactor

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Run `$how` and pin current behaviour with existing or characterization evidence.
2. Name the missing or incorrect domain boundary and the desired caller-facing shape.
3. Run `$architect` for a substantial boundary change and prefer subtraction over parallel abstractions.
4. Change one structural boundary at a time while keeping behaviour evidence green.
5. Migrate callers and remove superseded APIs; do not leave an indefinite dual path.
6. Prove behaviour equivalence and explain the reader-load improvement.
7. Do not mix intended behaviour changes into the refactor silently.
