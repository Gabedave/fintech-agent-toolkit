class Store:
    def __init__(self, enabled=True, expired=False):
        self.enabled = enabled
        self.now = 10
        self.expires_at = 0 if expired else 20
        self.payload = "synthetic content"
        self.sends = 0

    def expire(self):
        if self.expires_at <= self.now:
            self.payload = None

    def deliver(self):
        if self.payload is not None:
            self.sends += 1
