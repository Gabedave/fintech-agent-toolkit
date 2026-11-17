def run(queue):
    queue.complete_incoming()
    return {"removed": 0}
