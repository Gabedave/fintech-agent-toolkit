from copy import deepcopy


class Store:
    def __init__(self, card=None, restore_card=True):
        self.plan = {"card": card}
        self.restore_card = restore_card
        self.debits = 0

    def load_plan(self):
        return deepcopy(self.plan)

    def recover_card(self):
        plan = self.load_plan()
        if self.restore_card:
            plan["card"] = "recovered-card"
            self.plan = plan

    def finalize(self, plan):
        if plan["card"] is None:
            return "awaiting_card"
        self.debits += 1
        return "complete"
