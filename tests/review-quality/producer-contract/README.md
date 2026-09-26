# Verification classification

Replace the conservative all-review fallback with a classification of verification attempts. At least one successful verification requires human review (`review_required`); attempts without a success are terminal failures (`terminal_failed`). Support both current verification receipts and retained legacy HTTP receipts.

Run the existing checks with `python3 smoke.py`. Replay a scenario with `python3 observe.py '<JSON>'`. The JSON object requires `successful` and `legacy`, both booleans; no other fields are accepted. The replay produces a receipt through the local helper, then reports its `classification`.
