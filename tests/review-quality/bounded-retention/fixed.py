def run(queue):
    queue.complete_incoming()
    removed = queue.trim_completed(3)
    return {"removed": removed}
