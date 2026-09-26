# Current-system explanation

Use the smallest structure that makes the system understandable:

- **Overview:** the observable purpose and authoritative boundary.
- **Key concepts:** domain entities, states, ownership, and important data shapes.
- **Runtime path:** ordered calls and state transitions from entry point to outcome.
- **Where:** the source, tests, configuration, jobs, and operational surfaces that establish the model.
- **Failure and recovery:** validation, authorization, retry, timeout, concurrency, rollback, and cleanup where relevant.
- **Gotchas:** non-obvious constraints supported by evidence.
- **Design pressure:** concrete maintainability or correctness pressure, clearly separated from current behaviour.
- **Unknowns:** questions that available evidence did not settle and searches that returned no useful result.

Prefer links or exact file and symbol names over large copied code excerpts. A diagram is useful only when it materially clarifies three or more boundaries or state transitions.
