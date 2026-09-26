import json
import sys
import threading

import flow
from support import Store


def main():
    inputs = json.loads(sys.argv[1])
    if set(inputs) != {"workers"}:
        raise SystemExit("workers is required")
    workers = inputs["workers"]
    if (not isinstance(workers, list) or not 1 <= len(workers) <= 2 or
            len(workers) != len(set(workers)) or
            any(not isinstance(worker, str) or not worker for worker in workers)):
        raise SystemExit("workers must contain one or two distinct nonempty strings")

    store = Store()
    start = threading.Barrier(len(workers))
    results = []
    result_lock = threading.Lock()

    def run(worker):
        claimed = flow.claim(store, worker, start)
        with result_lock:
            results.append(claimed)

    threads = [threading.Thread(target=run, args=(worker,)) for worker in workers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=3)
    if any(thread.is_alive() for thread in threads):
        raise SystemExit("controlled interleaving did not complete")

    claims = sum(results)
    print(json.dumps({
        "claims": claims,
        "single_owner": claims == 1,
        "stored_owner": store.owner in workers,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
