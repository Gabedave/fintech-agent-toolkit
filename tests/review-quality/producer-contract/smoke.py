import unittest
from flow import classify
from support import records


class VerificationSmoke(unittest.TestCase):
    def test_legacy_success(self):
        self.assertEqual(classify(records(True, legacy=True)), "review_required")

    def test_mixed_legacy_attempts(self):
        attempts = records(False, legacy=True) + records(True, legacy=True)
        self.assertEqual(classify(attempts), "review_required")


if __name__ == "__main__":
    unittest.main()
