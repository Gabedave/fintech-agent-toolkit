import unittest
from flow import run
from support import Queue


class RetentionSmoke(unittest.TestCase):
    def test_small_queue(self):
        queue = Queue([1], [2], [3])
        self.assertEqual(run(queue), {"removed": 0})
        self.assertEqual(queue.completed, [1, 2])
        self.assertEqual(queue.waiting, [3])


if __name__ == "__main__":
    unittest.main()
