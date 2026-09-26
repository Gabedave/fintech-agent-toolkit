def claim(store, worker, start):
    observed_owner = store.owner
    start.wait(timeout=2)
    if observed_owner is None:
        store.owner = worker
        return True
    return False
