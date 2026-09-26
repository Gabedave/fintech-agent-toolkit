def run(store):
    plan = store.load_plan()
    if plan["card"] is None:
        store.recover_card()
        plan = store.load_plan()
    return store.finalize(plan)
