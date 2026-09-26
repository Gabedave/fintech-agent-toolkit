# Checkout recovery

Add missing-card recovery to checkout. A card that is already available or can be recovered should let checkout complete in one run, with exactly one debit. If no card is available, leave checkout awaiting a card without debiting.

Run the existing checks with `python3 smoke.py`. Replay a scenario with `python3 observe.py '<JSON>'`. The JSON object requires `card` (null or a nonempty string) and `restore_card` (boolean); no other fields are accepted. Observations contain the checkout `state`, stored `card`, and number of `debits`.
