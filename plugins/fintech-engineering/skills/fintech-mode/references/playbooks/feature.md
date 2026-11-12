# Feature

Read [delivery and authorization](../playbooks.md#delivery-and-authorization) before executing these steps, including direct entry.

1. Identify the user-visible outcome, public seam, compatibility constraints, and named domain data shape.
2. Run `$how`, then `$architect` when the routing contract identifies an architectural boundary.
3. Check ownership, independent workstreams, shared mutable state, and the smallest safe decomposition before implementation.
4. Settle observable uncertainty with a bounded throwaway prototype when cheaper than speculation.
5. Deliver one thin end-to-end behaviour path.
6. Cover contracts, compatibility, negative paths, retries, and recovery before adding breadth.
7. Run the repository verifier and maintain its map when the proof boundary changed.
