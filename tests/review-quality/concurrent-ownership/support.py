import threading


class Store:
    def __init__(self):
        self.owner = None
        self.lock = threading.Lock()
