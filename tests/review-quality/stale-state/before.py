def run(store):
    plan = store.load_plan()
    if plan["card"] is None:
        return "awaiting_card"
    return store.finalize(plan)
