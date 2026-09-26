def claim(store, worker, start):
    start.wait(timeout=2)
    with store.lock:
        if store.owner is not None:
            return False
        store.owner = worker
        return True
