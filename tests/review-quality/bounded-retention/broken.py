def run(queue):
    queue.complete_incoming()
    if len(queue.completed) > 3:
        return {"removed": 0}
    return {"removed": 0}
