# Design record

Keep the record compact and decision-oriented:

- **Outcome and constraints**
- **Current seam and pressure**
- **Domain model and invariants**
- **Alternative A:** caller shape, ownership, failure/recovery, migration, verification, trade-offs
- **Alternative B:** caller shape, ownership, failure/recovery, migration, verification, trade-offs
- **Decision:** selected design and decisive evidence
- **Rejected directions:** why they were not selected
- **Invalidation signals:** implementation or runtime evidence that should force redesign
- **Rollout and rollback:** ordering where contracts, schemas, data, or repositories differ

Use [the decision-record policy](decision-records.md) to decide whether this rationale belongs in a permanent repository ADR or the task/PR. Do not create a permanent document for routine internal choices. Use `$work-continuity` for the execution trail of long-running or handed-off work; it does not replace an ADR for a lasting decision.
