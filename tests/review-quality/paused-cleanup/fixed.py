def run(store):
    store.expire()
    if not store.enabled:
        return
    store.deliver()
