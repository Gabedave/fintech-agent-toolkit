class Queue:
    def __init__(self, completed, incoming, waiting):
        self.completed = list(completed)
        self.incoming = list(incoming)
        self.waiting = list(waiting)

    def complete_incoming(self):
        self.completed.extend(self.incoming)
        self.incoming.clear()

    def trim_completed(self, limit):
        removed = max(0, len(self.completed) - limit)
        if removed:
            del self.completed[:removed]
        return removed
