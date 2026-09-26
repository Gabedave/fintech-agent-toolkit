def run(store):
    if not store.enabled:
        return
    store.expire()
    store.deliver()
