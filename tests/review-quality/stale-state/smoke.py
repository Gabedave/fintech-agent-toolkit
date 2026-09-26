import unittest
from flow import run
from support import Store


class CheckoutSmoke(unittest.TestCase):
    def test_existing_card(self):
        store = Store(card="existing-card")
        self.assertEqual(run(store), "complete")
        self.assertEqual(store.debits, 1)

    def test_no_card_available(self):
        store = Store(restore_card=False)
        self.assertEqual(run(store), "awaiting_card")
        self.assertEqual(store.debits, 0)


if __name__ == "__main__":
    unittest.main()
