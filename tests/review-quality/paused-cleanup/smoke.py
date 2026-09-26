import unittest
from flow import run
from support import Store


class DeliverySmoke(unittest.TestCase):
    def test_enabled_fresh_content(self):
        store = Store()
        run(store)
        self.assertEqual((store.payload, store.sends), ("synthetic content", 1))

    def test_enabled_expired_content(self):
        store = Store(expired=True)
        run(store)
        self.assertEqual((store.payload, store.sends), (None, 0))


if __name__ == "__main__":
    unittest.main()
