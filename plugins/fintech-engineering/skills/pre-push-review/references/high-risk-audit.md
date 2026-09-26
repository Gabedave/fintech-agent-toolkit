# High-risk audit

Read this reference only when the candidate is high risk.

The pre-edit implementation-readiness table is an input to this audit, not a parallel approval system. Reuse its named reproductions and tests, then account for every area below. For each area retain the authoritative invariant, changed seam, executable evidence, and `confirmed`, `not-applicable`, `unverified`, or `failed` status. A `not-applicable` entry needs brief disqualifying domain evidence; do not silently omit an area.

- states, allowed transitions, and terminal states;
- ownership, authorization, tenant boundaries, and competing actors;
- transaction, commit, and rollback boundaries;
- known success, known failure, and unknown external outcomes;
- retries, idempotency, deduplication, and partial completion;
- authoritative clocks, deadlines, leases, and expiry behavior;
- recovery, reconciliation, observability, and manual gates. This is one compound audit area: it is applicable when any one of those concerns exists and `not-applicable` only when all four are absent.

Trace applicable invariants through source and tests. Explicitly examine actor interleavings, stale reads or writes, partial commits, retries after interruption, ambiguous provider responses, and clock-boundary behavior. For concurrency or timing, require deterministic coordination such as barriers, controlled clocks, transaction hooks, or equivalent synchronization; sleeps, repeated retries, and stress runs may supplement but cannot be the sole proof.

Apply verdict precedence consistently. A reproduced Critical or Major blocker, failed criterion, or failed invariant makes the candidate `NOT READY FOR TEAM REVIEW`; residual partial or unverified evidence remains visible but does not dilute that definitive rejection. When no definitive blocker is established but a material authoritative invariant or criterion cannot be established safely, use `REVIEW INCOMPLETE`. Use `READY FOR TEAM REVIEW` only when every material criterion and applicable invariant is confirmed and no blocker remains.
