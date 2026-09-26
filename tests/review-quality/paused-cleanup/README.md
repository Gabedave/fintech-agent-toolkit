# Delivery pause

Add an operational switch that pauses delivery. Pausing must prevent sends while scheduled retention maintenance continues. Expired content must be cleared, and enabled delivery must retain its existing behavior for unexpired content.

For this contained flow, retention maintenance is the recovery behavior while delivery is paused. The complete observable post-state is the retained payload plus the send count, so cleanup must remain visible even when no delivery occurs.

Run the existing checks with `python3 smoke.py`. Replay a scenario with `python3 observe.py '<JSON>'`. The JSON object requires `enabled` and `expired`, both booleans; no other fields are accepted. The clock is fixed for the replay, which reports the retained `payload` and the number of `sends`.
