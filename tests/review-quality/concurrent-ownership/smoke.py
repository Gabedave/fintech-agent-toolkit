import threading
import unittest

import flow
from support import Store


class ClaimSmoke(unittest.TestCase):
    def test_sequential_claim_does_not_replace_owner(self):
        store = Store()
        self.assertTrue(flow.claim(store, "alpha", threading.Barrier(1)))
        self.assertFalse(flow.claim(store, "beta", threading.Barrier(1)))
        self.assertEqual(store.owner, "alpha")


if __name__ == "__main__":
    unittest.main()
