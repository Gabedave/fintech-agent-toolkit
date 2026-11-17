# Bounded completed-job retention

Maintain a queue after new jobs complete. Retain only the three newest completed jobs; waiting
jobs must remain untouched. Return the aggregate number of completed records removed, including
zero when no cleanup was needed, so operations can distinguish a healthy empty run from a stalled
cleanup. This fixture models transient queue records; durable business state lives elsewhere.

## Pre-edit resource lifecycle record

- Workload: synthetic single-worker batches of up to eight completed and eight incoming jobs;
  peak input is sixteen terminal records before cleanup. No replica shares this in-memory queue.
- Ceiling: three retained terminal records after each run. Waiting jobs are not subject to this
  ceiling and are never removed by terminal cleanup.
- Cleanup and safe limit: trim oldest terminal records after completion; keep durable business
  state elsewhere and preserve all waiting jobs. The next run remains safe at the ceiling.
- Proof: the small-queue smoke control and a documented oversized `observe.py` replay establish
  both no-op and pruning behavior. The aggregate `removed` count is the rollout signal, including
  zero on an empty cleanup run.

Run the existing checks with `python3 smoke.py`. Replay a case with `python3 observe.py '<JSON>'`.
The JSON object requires arrays of distinct integer job IDs named `completed`, `incoming`, and
`waiting`. Each array has at most eight items. The output reports those arrays after maintenance
and the aggregate `removed` count.
