# Concurrent ownership

Allow a worker to claim an available job. When two distinct workers contend at the same time, exactly one may report success and become the stored owner. A later or competing claim must fail without replacing that owner.

Run the existing checks with `python3 smoke.py`. Replay a controlled interleaving with `python3 observe.py '<JSON>'`. The JSON object requires `workers`, an array containing one or two distinct nonempty worker IDs; no other fields are accepted. The replay releases every worker from the same barrier and reports the number of successful claims, whether ownership was unique, and whether the store retained a submitted owner.
